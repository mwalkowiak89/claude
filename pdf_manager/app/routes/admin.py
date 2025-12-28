import os
import uuid
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
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


@admin_bp.route('/access')
@login_required
@admin_required
def access_overview():
    """Overview of all file access permissions."""
    files = File.query.order_by(File.filename).all()
    users = User.query.filter_by(is_admin=False).order_by(User.email).all()

    # Create access matrix
    access_matrix = {}
    for file in files:
        access_matrix[file.id] = set()
        for access in file.user_access:
            access_matrix[file.id].add(access.user_id)

    return render_template(
        'admin/access_overview.html',
        title='Przegląd uprawnień',
        files=files,
        users=users,
        access_matrix=access_matrix
    )
