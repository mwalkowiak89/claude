import os
import uuid
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, User, File, UserFileAccess, EmailTemplate, LANGUAGES, TEMPLATE_TYPES, AppSettings, FileDownload
from app.forms import (
    RegistrationForm, FileUploadForm, FileUpdateForm,
    FileAccessForm, EditUserForm, ChangePasswordForm, EmailTemplateForm,
    BackupRestoreForm, AppSettingsForm
)
from app.email import send_file_update_notification, send_bulk_access_notifications
from app import limiter

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Apply rate limiting to all admin routes
admin_limiter = limiter.shared_limit("100 per minute", scope="admin")


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
@admin_limiter
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
@admin_limiter
def users():
    """List all users."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', title='Użytkownicy', users=users)


@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
@limiter.limit("20 per hour")
def add_user():
    """Add a new user."""
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower(),
            is_admin=form.is_admin.data,
            preferred_language=form.preferred_language.data
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
        user.preferred_language = form.preferred_language.data
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
@admin_limiter
def files():
    """List all files."""
    files = File.query.order_by(File.upload_date.desc()).all()
    return render_template('admin/files.html', title='Pliki', files=files)


@admin_bp.route('/files/upload', methods=['GET', 'POST'])
@login_required
@admin_required
@limiter.limit("30 per hour")
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
@admin_limiter
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

        # Track new permissions for email notifications: {user: [files]}
        new_access_map = {}

        # Pre-fetch users and files for efficiency
        users_dict = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
        files_dict = {f.id: f for f in File.query.filter(File.id.in_(file_ids)).all()}

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

                    # Track for email notification
                    user = users_dict.get(user_id)
                    file = files_dict.get(file_id)
                    if user and file:
                        if user not in new_access_map:
                            new_access_map[user] = []
                        new_access_map[user].append(file)

        db.session.commit()

        # Send email notifications for new access
        notified_count = 0
        if new_access_map:
            login_url = url_for('auth.login', _external=True)
            notified_count = send_bulk_access_notifications(new_access_map, login_url)

        # Flash messages
        if added_count > 0:
            if notified_count > 0:
                flash(f'Dodano {added_count} nowych uprawnień. Wysłano powiadomienia do {notified_count} użytkowników.', 'success')
            else:
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


@admin_bp.route('/api/user/<int:user_id>/files')
@login_required
@admin_required
def api_user_files(user_id):
    """API endpoint to get files a user has access to."""
    user = User.query.get_or_404(user_id)

    file_ids = [access.file_id for access in user.file_access]

    return jsonify({'file_ids': file_ids})


@admin_bp.route('/api/users/files')
@login_required
@admin_required
def api_users_files():
    """API endpoint to get files for multiple users (intersection)."""
    user_ids = request.args.getlist('user_ids', type=int)

    if not user_ids:
        return jsonify({'file_ids': [], 'common_file_ids': [], 'user_file_map': {}})

    # Get file access for each user
    user_file_map = {}
    all_file_sets = []

    for user_id in user_ids:
        user = User.query.get(user_id)
        if user:
            file_ids = set(access.file_id for access in user.file_access)
            user_file_map[user_id] = list(file_ids)
            all_file_sets.append(file_ids)

    # Find common files (intersection of all users' files)
    if all_file_sets:
        common_file_ids = list(set.intersection(*all_file_sets)) if len(all_file_sets) > 1 else list(all_file_sets[0])
    else:
        common_file_ids = []

    # All files any selected user has access to (union)
    all_file_ids = list(set.union(*all_file_sets)) if all_file_sets else []

    return jsonify({
        'file_ids': all_file_ids,
        'common_file_ids': common_file_ids,
        'user_file_map': user_file_map
    })


# ===== EMAIL TEMPLATES =====

@admin_bp.route('/email-templates')
@login_required
@admin_required
def email_templates():
    """List and manage email templates."""
    template_type = request.args.get('type', 'new_access')
    language = request.args.get('lang', 'pl')

    # Get current template
    template = EmailTemplate.query.filter_by(
        template_type=template_type,
        language=language
    ).first()

    # Get all templates for counts
    all_templates = EmailTemplate.query.all()
    template_counts = {}
    for t in all_templates:
        key = f"{t.template_type}:{t.language}"
        template_counts[key] = True

    return render_template(
        'admin/email_templates.html',
        title='Szablony Email',
        template=template,
        current_type=template_type,
        current_language=language,
        languages=LANGUAGES,
        template_types=TEMPLATE_TYPES,
        template_counts=template_counts
    )


@admin_bp.route('/email-templates/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_email_template():
    """Edit a specific email template."""
    template_type = request.args.get('type', 'new_access')
    language = request.args.get('lang', 'pl')

    # Get or create template
    template = EmailTemplate.query.filter_by(
        template_type=template_type,
        language=language
    ).first()

    form = EmailTemplateForm()

    if request.method == 'GET' and template:
        form.subject.data = template.subject
        form.body.data = template.body

    if form.validate_on_submit():
        if template:
            template.subject = form.subject.data
            template.body = form.body.data
        else:
            # Get variables from default template
            default_vars = '{user_name}, {file_list}, {file_count}, {login_url}'
            if template_type == 'file_update':
                default_vars = '{user_name}, {file_name}, {file_version}, {file_description}, {login_url}'

            template = EmailTemplate(
                template_type=template_type,
                language=language,
                subject=form.subject.data,
                body=form.body.data,
                variables=default_vars
            )
            db.session.add(template)

        db.session.commit()
        flash('Szablon został zapisany.', 'success')
        return redirect(url_for('admin.email_templates', type=template_type, lang=language))

    # Get type and language display names
    type_display = dict(TEMPLATE_TYPES).get(template_type, template_type)
    lang_display = dict(LANGUAGES).get(language, language)

    # Get variables info
    variables = '{user_name}, {file_list}, {file_count}, {login_url}'
    if template_type == 'file_update':
        variables = '{user_name}, {file_name}, {file_version}, {file_description}, {login_url}'
    if template:
        variables = template.variables or variables

    return render_template(
        'admin/email_template_edit.html',
        title=f'Edytuj szablon - {type_display} ({lang_display})',
        form=form,
        template=template,
        template_type=template_type,
        language=language,
        type_display=type_display,
        lang_display=lang_display,
        variables=variables
    )


@admin_bp.route('/email-templates/preview')
@login_required
@admin_required
def preview_email_template():
    """Preview email template with sample data."""
    template_type = request.args.get('type', 'new_access')
    language = request.args.get('lang', 'pl')

    template = EmailTemplate.query.filter_by(
        template_type=template_type,
        language=language
    ).first()

    if not template:
        return jsonify({'error': 'Template not found'}), 404

    # Sample data for preview
    if template_type == 'new_access':
        context = {
            'user_name': 'jan.kowalski@example.com',
            'file_count': '3',
            'file_list': '''<ul style="list-style: none; padding: 0;">
                <li style="margin-bottom: 10px;">• <strong>Instrukcja_obslugi.pdf</strong> (v2.1) - Instrukcja obsługi systemu</li>
                <li style="margin-bottom: 10px;">• <strong>Raport_Q4_2024.pdf</strong> (v1.0) - Raport kwartalny</li>
                <li style="margin-bottom: 10px;">• <strong>Procedury_BHP.pdf</strong> (v3.2) - Procedury bezpieczeństwa</li>
            </ul>''',
            'login_url': 'https://example.com/login'
        }
    else:  # file_update
        context = {
            'user_name': 'jan.kowalski@example.com',
            'file_name': 'Instrukcja_obslugi.pdf',
            'file_version': '2.1',
            'file_description': '<p><em>Opis zmian:</em> Zaktualizowano rozdział 3 dotyczący nowych funkcji.</p>',
            'login_url': 'https://example.com/login'
        }

    subject, body = template.render(context)

    # Wrap body in email HTML structure
    html_preview = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 20px auto; padding: 20px; background: #f5f5f5; }}
            .email-container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .email-subject {{ background: #0d6efd; color: white; padding: 15px; border-radius: 8px 8px 0 0; margin: -20px -20px 20px -20px; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-subject"><strong>Temat:</strong> {subject}</div>
            {body}
        </div>
    </body>
    </html>
    '''

    return html_preview


@admin_bp.route('/email-templates/reset', methods=['POST'])
@login_required
@admin_required
def reset_email_template():
    """Reset template to default."""
    from app.models import seed_email_templates

    template_type = request.form.get('type', 'new_access')
    language = request.form.get('lang', 'pl')

    # Delete existing template
    EmailTemplate.query.filter_by(
        template_type=template_type,
        language=language
    ).delete()
    db.session.commit()

    # Seed will recreate the default
    seed_email_templates()

    flash('Szablon został przywrócony do domyślnego.', 'success')
    return redirect(url_for('admin.email_templates', type=template_type, lang=language))


# ===== BACKUP MANAGEMENT =====

@admin_bp.route('/backups')
@login_required
@admin_required
@admin_limiter
def backups():
    """List all backups."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from backup import list_backups, DAILY_BACKUP_DIR

    backup_list = list_backups()

    # Calculate total size
    total_size = sum(b['size_mb'] for b in backup_list)

    # Get last backup info
    last_backup = backup_list[0] if backup_list else None

    return render_template(
        'admin/backups.html',
        title='Kopie zapasowe',
        backups=backup_list,
        total_size=round(total_size, 2),
        last_backup=last_backup,
        backup_count=len(backup_list)
    )


@admin_bp.route('/backups/create', methods=['POST'])
@login_required
@admin_required
@limiter.limit("5 per hour")
def create_backup():
    """Create a new backup manually."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from backup import create_backup as do_create_backup

    try:
        # Change to project directory for backup
        original_dir = os.getcwd()
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        os.chdir(project_dir)

        try:
            backup_info = do_create_backup(notify_admins=False)
            flash(f'Backup utworzony: {backup_info["filename"]} ({backup_info["size_mb"]:.2f} MB)', 'success')
        finally:
            os.chdir(original_dir)

    except Exception as e:
        flash(f'Błąd tworzenia backupu: {str(e)}', 'danger')

    return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/<filename>/download')
@login_required
@admin_required
def download_backup(filename):
    """Download a backup file."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from backup import get_backup_path

    # Validate filename (prevent directory traversal)
    if '..' in filename or '/' in filename or '\\' in filename:
        abort(400)

    if not filename.startswith('backup_') or not filename.endswith('.zip'):
        abort(400)

    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    backup_path = os.path.join(project_dir, 'backups', 'daily', filename)

    if not os.path.exists(backup_path):
        flash('Backup nie znaleziony.', 'danger')
        return redirect(url_for('admin.backups'))

    return send_file(
        backup_path,
        as_attachment=True,
        download_name=filename
    )


@admin_bp.route('/backups/<filename>/delete', methods=['POST'])
@login_required
@admin_required
def delete_backup(filename):
    """Delete a backup file."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from backup import delete_backup as do_delete_backup, DAILY_BACKUP_DIR

    # Validate filename
    if '..' in filename or '/' in filename or '\\' in filename:
        abort(400)

    if not filename.startswith('backup_') or not filename.endswith('.zip'):
        abort(400)

    try:
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        original_dir = os.getcwd()
        os.chdir(project_dir)

        try:
            do_delete_backup(filename)
            flash(f'Backup usunięty: {filename}', 'success')
        finally:
            os.chdir(original_dir)

    except FileNotFoundError:
        flash('Backup nie znaleziony.', 'danger')
    except Exception as e:
        flash(f'Błąd usuwania backupu: {str(e)}', 'danger')

    return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/<filename>/restore', methods=['GET', 'POST'])
@login_required
@admin_required
def restore_backup(filename):
    """Restore from a backup file."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from backup import restore_backup as do_restore_backup, get_backup_info, DAILY_BACKUP_DIR

    # Validate filename
    if '..' in filename or '/' in filename or '\\' in filename:
        abort(400)

    if not filename.startswith('backup_') or not filename.endswith('.zip'):
        abort(400)

    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    backup_path = os.path.join(project_dir, 'backups', 'daily', filename)

    if not os.path.exists(backup_path):
        flash('Backup nie znaleziony.', 'danger')
        return redirect(url_for('admin.backups'))

    # Get backup info
    from pathlib import Path
    backup_info = get_backup_info(Path(backup_path))

    form = BackupRestoreForm()

    if form.validate_on_submit():
        # Verify password
        if not current_user.check_password(form.password.data):
            flash('Nieprawidłowe hasło.', 'danger')
            return render_template(
                'admin/backup_restore.html',
                title='Przywróć backup',
                form=form,
                backup=backup_info,
                filename=filename
            )

        # Verify confirmation
        if form.confirmation.data.strip().upper() != 'PRZYWRÓĆ':
            flash('Nieprawidłowe potwierdzenie. Wpisz PRZYWRÓĆ.', 'danger')
            return render_template(
                'admin/backup_restore.html',
                title='Przywróć backup',
                form=form,
                backup=backup_info,
                filename=filename
            )

        try:
            original_dir = os.getcwd()
            os.chdir(project_dir)

            try:
                result = do_restore_backup(filename)
                flash(f'Backup przywrócony pomyślnie! Przywrócono {result["files_restored"]} plików. Zaloguj się ponownie.', 'success')

                # Force logout after restore
                from flask_login import logout_user
                logout_user()
                return redirect(url_for('auth.login'))

            finally:
                os.chdir(original_dir)

        except Exception as e:
            flash(f'Błąd przywracania backupu: {str(e)}', 'danger')
            return redirect(url_for('admin.backups'))

    return render_template(
        'admin/backup_restore.html',
        title='Przywróć backup',
        form=form,
        backup=backup_info,
        filename=filename
    )


# ===== APP SETTINGS (BRANDING) =====

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """Application branding settings."""
    settings = AppSettings.get_settings()
    form = AppSettingsForm(obj=settings)

    if form.validate_on_submit():
        settings.app_name = form.app_name.data
        settings.primary_color = form.primary_color.data
        settings.navbar_color = form.navbar_color.data
        settings.enable_custom_branding = form.enable_custom_branding.data

        # Handle logo upload
        if form.logo.data:
            from app.utils import resize_logo

            file = form.logo.data
            # Validate file size (2MB max)
            file.seek(0, 2)  # Seek to end
            size = file.tell()
            file.seek(0)  # Reset

            if size > 2 * 1024 * 1024:
                flash('Logo jest za duże. Maksymalny rozmiar: 2MB.', 'danger')
                return render_template(
                    'admin/settings.html',
                    title='Ustawienia aplikacji',
                    form=form,
                    settings=settings
                )

            # Save logo
            original_filename = secure_filename(file.filename)
            ext = original_filename.rsplit('.', 1)[-1].lower()
            logo_filename = f"logo_{uuid.uuid4().hex[:8]}.{ext}"

            branding_dir = os.path.join(current_app.static_folder, 'uploads', 'branding')
            os.makedirs(branding_dir, exist_ok=True)

            # Save original first
            temp_path = os.path.join(branding_dir, f"temp_{logo_filename}")
            file.save(temp_path)

            # Resize if not SVG
            final_path = os.path.join(branding_dir, logo_filename)
            if ext != 'svg':
                try:
                    resize_logo(temp_path, final_path, max_width=200)
                    os.remove(temp_path)
                except Exception as e:
                    flash(f'Błąd przetwarzania logo: {str(e)}', 'danger')
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return render_template(
                        'admin/settings.html',
                        title='Ustawienia aplikacji',
                        form=form,
                        settings=settings
                    )
            else:
                os.rename(temp_path, final_path)

            # Remove old logo if exists
            if settings.logo_filename:
                old_logo_path = os.path.join(branding_dir, settings.logo_filename)
                if os.path.exists(old_logo_path):
                    os.remove(old_logo_path)

            settings.logo_filename = logo_filename

        db.session.commit()
        flash('Ustawienia zostały zapisane.', 'success')
        return redirect(url_for('admin.settings'))

    return render_template(
        'admin/settings.html',
        title='Ustawienia aplikacji',
        form=form,
        settings=settings
    )


@admin_bp.route('/settings/delete-logo', methods=['POST'])
@login_required
@admin_required
def delete_logo():
    """Delete the current logo."""
    settings = AppSettings.get_settings()

    if settings.logo_filename:
        logo_path = os.path.join(
            current_app.static_folder, 'uploads', 'branding', settings.logo_filename
        )
        if os.path.exists(logo_path):
            os.remove(logo_path)

        settings.logo_filename = None
        db.session.commit()
        flash('Logo zostało usunięte.', 'success')

    return redirect(url_for('admin.settings'))


@admin_bp.route('/settings/reset', methods=['POST'])
@login_required
@admin_required
def reset_settings():
    """Reset all settings to defaults."""
    settings = AppSettings.get_settings()

    # Delete logo file if exists
    if settings.logo_filename:
        logo_path = os.path.join(
            current_app.static_folder, 'uploads', 'branding', settings.logo_filename
        )
        if os.path.exists(logo_path):
            os.remove(logo_path)

    AppSettings.reset_to_defaults()
    flash('Przywrócono domyślne ustawienia.', 'success')
    return redirect(url_for('admin.settings'))


# ===== DOWNLOAD LOGS =====

@admin_bp.route('/download-logs')
@login_required
@admin_required
@admin_limiter
def download_logs():
    """View file download audit logs."""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Filters
    user_id = request.args.get('user_id', type=int)
    file_id = request.args.get('file_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # Build query
    query = FileDownload.query

    if user_id:
        query = query.filter(FileDownload.user_id == user_id)
    if file_id:
        query = query.filter(FileDownload.file_id == file_id)
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(FileDownload.downloaded_at >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.filter(FileDownload.downloaded_at <= to_date)
        except ValueError:
            pass

    # Order by most recent first
    query = query.order_by(FileDownload.downloaded_at.desc())

    # Paginate
    downloads = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get all users and files for filter dropdowns
    users = User.query.order_by(User.email).all()
    files = File.query.order_by(File.filename).all()

    # Calculate suspicious users (more than 5 downloads of same file in last hour)
    from datetime import timedelta
    suspicious_downloads = {}
    recent_cutoff = datetime.utcnow() - timedelta(hours=1)

    for download in downloads.items:
        key = f"{download.user_id}:{download.file_id}"
        if key not in suspicious_downloads:
            count = FileDownload.query.filter(
                FileDownload.user_id == download.user_id,
                FileDownload.file_id == download.file_id,
                FileDownload.downloaded_at > recent_cutoff
            ).count()
            suspicious_downloads[key] = count > 5

    return render_template(
        'admin/download_logs.html',
        title='Historia pobrań',
        downloads=downloads,
        users=users,
        files=files,
        suspicious_downloads=suspicious_downloads,
        filter_user_id=user_id,
        filter_file_id=file_id,
        filter_date_from=date_from,
        filter_date_to=date_to
    )


@admin_bp.route('/download-logs/export')
@login_required
@admin_required
def export_download_logs():
    """Export download logs to CSV."""
    import csv
    from io import StringIO

    # Get all downloads (with filters)
    user_id = request.args.get('user_id', type=int)
    file_id = request.args.get('file_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    query = FileDownload.query

    if user_id:
        query = query.filter(FileDownload.user_id == user_id)
    if file_id:
        query = query.filter(FileDownload.file_id == file_id)
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(FileDownload.downloaded_at >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.filter(FileDownload.downloaded_at <= to_date)
        except ValueError:
            pass

    downloads = query.order_by(FileDownload.downloaded_at.desc()).all()

    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID Pobrania', 'Użytkownik', 'Plik', 'Data/Czas', 'Adres IP', 'User Agent'])

    for download in downloads:
        writer.writerow([
            download.download_id,
            download.user.email if download.user else 'N/A',
            download.file.original_filename if download.file else 'N/A',
            download.downloaded_at.strftime('%Y-%m-%d %H:%M:%S'),
            download.ip_address or 'N/A',
            download.user_agent or 'N/A'
        ])

    output.seek(0)

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=download_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )
