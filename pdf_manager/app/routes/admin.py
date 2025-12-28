import os
import uuid
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, User, File, UserFileAccess
from app.forms import (
    RegistrationForm, FileUploadForm, FileUpdateForm,
    FileAccessForm, EditUserForm, ChangePasswordForm
)
from app.email import send_file_update_notification

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Admin dashboard."""
    stats = {
        'users': User.query.count(),
        'files': File.query.count(),
        'access_grants': UserFileAccess.query.count()
    }
    recent_files = File.query.order_by(File.upload_date.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        title='Panel administracyjny',
        stats=stats,
        recent_files=recent_files,
        recent_users=recent_users
    )


# ===== USER MANAGEMENT =====

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """List all users."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', title='Użytkownicy', users=users)


@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Add a new user."""
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower(),
            is_admin=form.is_admin.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'Użytkownik {user.email} został utworzony.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', title='Dodaj użytkownika', form=form)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user details."""
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)

    if form.validate_on_submit():
        # Check if email is taken by another user
        existing = User.query.filter_by(email=form.email.data.lower()).first()
        if existing and existing.id != user_id:
            flash('Ten adres email jest już zajęty.', 'danger')
            return render_template('admin/user_form.html', title='Edytuj użytkownika', form=form, user=user)

        user.email = form.email.data.lower()
        user.is_admin = form.is_admin.data
        db.session.commit()
        flash('Dane użytkownika zostały zaktualizowane.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', title='Edytuj użytkownika', form=form, user=user)


@admin_bp.route('/users/<int:user_id>/password', methods=['GET', 'POST'])
@login_required
@admin_required
def change_user_password(user_id):
    """Change user password."""
    user = User.query.get_or_404(user_id)
    form = ChangePasswordForm()

    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        db.session.commit()
        flash(f'Hasło dla {user.email} zostało zmienione.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/change_password.html', title='Zmień hasło', form=form, user=user)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user."""
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('Nie możesz usunąć własnego konta.', 'danger')
        return redirect(url_for('admin.users'))

    db.session.delete(user)
    db.session.commit()
    flash(f'Użytkownik {user.email} został usunięty.', 'success')
    return redirect(url_for('admin.users'))


# ===== FILE MANAGEMENT =====

@admin_bp.route('/files')
@login_required
@admin_required
def files():
    """List all files."""
    files = File.query.order_by(File.upload_date.desc()).all()
    return render_template('admin/files.html', title='Pliki', files=files)


@admin_bp.route('/files/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_file():
    """Upload a new file."""
    form = FileUploadForm()
    if form.validate_on_submit():
        file = form.file.data
        original_filename = secure_filename(file.filename)

        # Generate unique filename
        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)

        # Save file
        file.save(file_path)

        # Create database record
        new_file = File(
            filename=original_filename,
            original_filename=original_filename,
            version=1,
            file_path=unique_filename,
            description=form.description.data
        )
        db.session.add(new_file)
        db.session.commit()

        flash(f'Plik {original_filename} został przesłany.', 'success')
        return redirect(url_for('admin.files'))

    return render_template('admin/file_upload.html', title='Prześlij plik', form=form)


@admin_bp.route('/files/<int:file_id>/update', methods=['GET', 'POST'])
@login_required
@admin_required
def update_file(file_id):
    """Update file (upload new version)."""
    existing_file = File.query.get_or_404(file_id)
    form = FileUpdateForm()

    if form.validate_on_submit():
        file = form.file.data

        # Generate unique filename
        unique_filename = f"{uuid.uuid4().hex}_{existing_file.original_filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)

        # Save new file
        file.save(file_path)

        # Update database record
        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], existing_file.file_path)
        existing_file.file_path = unique_filename
        existing_file.version += 1
        existing_file.upload_date = datetime.utcnow()
        if form.description.data:
            existing_file.description = form.description.data

        db.session.commit()

        # Remove old file
        if os.path.exists(old_path):
            os.remove(old_path)

        # Notify users with access
        users_with_access = existing_file.get_users_with_access()
        if users_with_access:
            send_file_update_notification(existing_file, users_with_access)

        flash(f'Plik {existing_file.filename} został zaktualizowany do wersji {existing_file.version}.', 'success')
        return redirect(url_for('admin.files'))

    return render_template(
        'admin/file_update.html',
        title='Aktualizuj plik',
        form=form,
        file=existing_file
    )


@admin_bp.route('/files/<int:file_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_file(file_id):
    """Delete a file."""
    file = File.query.get_or_404(file_id)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.file_path)

    # Remove physical file
    if os.path.exists(file_path):
        os.remove(file_path)

    # Remove database record
    db.session.delete(file)
    db.session.commit()

    flash(f'Plik {file.filename} został usunięty.', 'success')
    return redirect(url_for('admin.files'))


# ===== ACCESS MANAGEMENT =====

@admin_bp.route('/files/<int:file_id>/access', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_access(file_id):
    """Manage user access to a file."""
    file = File.query.get_or_404(file_id)
    form = FileAccessForm()

    # Get non-admin users for the selection
    users = User.query.filter_by(is_admin=False).order_by(User.email).all()
    form.users.choices = [(u.id, u.email) for u in users]

    if request.method == 'GET':
        # Pre-select users who already have access
        form.users.data = [access.user_id for access in file.user_access]

    if form.validate_on_submit():
        # Remove all existing access
        UserFileAccess.query.filter_by(file_id=file_id).delete()

        # Add new access
        for user_id in form.users.data:
            access = UserFileAccess(user_id=user_id, file_id=file_id)
            db.session.add(access)

        db.session.commit()
        flash('Uprawnienia zostały zaktualizowane.', 'success')
        return redirect(url_for('admin.files'))

    return render_template(
        'admin/access_form.html',
        title='Zarządzaj dostępem',
        form=form,
        file=file
    )


@admin_bp.route('/access', methods=['GET', 'POST'])
@login_required
@admin_required
def access_overview():
    """Bulk access management interface."""
    if request.method == 'POST':
        # Get selected users and files
        user_ids = request.form.getlist('users', type=int)
        file_ids = request.form.getlist('files', type=int)

        if not user_ids or not file_ids:
            flash('Musisz wybrać co najmniej jednego użytkownika i jeden plik.', 'warning')
            return redirect(url_for('admin.access_overview'))

        # Count how many new permissions were added
        added_count = 0
        skipped_count = 0

        for user_id in user_ids:
            for file_id in file_ids:
                # Check if access already exists
                existing = UserFileAccess.query.filter_by(
                    user_id=user_id,
                    file_id=file_id
                ).first()

                if existing:
                    skipped_count += 1
                else:
                    access = UserFileAccess(user_id=user_id, file_id=file_id)
                    db.session.add(access)
                    added_count += 1

        db.session.commit()

        if added_count > 0:
            flash(f'Dodano {added_count} nowych uprawnień.', 'success')
        if skipped_count > 0:
            flash(f'Pominięto {skipped_count} istniejących uprawnień.', 'info')

        return redirect(url_for('admin.access_overview'))

    # GET request - display the form
    files = File.query.order_by(File.filename).all()
    users = User.query.filter_by(is_admin=False).order_by(User.email).all()

    # Add file count for each user
    user_file_counts = {}
    for user in users:
        user_file_counts[user.id] = user.file_access.count()

    # Add user count for each file
    file_user_counts = {}
    for file in files:
        file_user_counts[file.id] = file.user_access.count()

    return render_template(
        'admin/access_overview.html',
        title='Zarządzaj uprawnieniami',
        files=files,
        users=users,
        user_file_counts=user_file_counts,
        file_user_counts=file_user_counts
    )


@admin_bp.route('/api/users/search')
@login_required
@admin_required
def api_search_users():
    """API endpoint for live user search."""
    query = request.args.get('q', '').strip().lower()

    users_query = User.query.filter_by(is_admin=False)

    if query:
        users_query = users_query.filter(User.email.ilike(f'%{query}%'))

    users = users_query.order_by(User.email).all()

    result = []
    for user in users:
        result.append({
            'id': user.id,
            'email': user.email,
            'file_count': user.file_access.count()
        })

    return jsonify(result)
