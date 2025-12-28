import os
from flask import Blueprint, render_template, send_file, abort, current_app
from flask_login import login_required, current_user
from app.models import File, UserFileAccess

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    """Display user's accessible files."""
    if current_user.is_admin:
        # Admin sees all files
        files = File.query.order_by(File.upload_date.desc()).all()
    else:
        # Regular user sees only files they have access to
        files = File.query.join(UserFileAccess).filter(
            UserFileAccess.user_id == current_user.id
        ).order_by(File.upload_date.desc()).all()

    return render_template('main/index.html', title='Moje pliki', files=files)


@main_bp.route('/file/<int:file_id>')
@login_required
def view_file(file_id):
    """View file details."""
    file = File.query.get_or_404(file_id)

    # Check access
    if not current_user.has_access_to(file):
        abort(403)

    return render_template('main/file_view.html', title=file.filename, file=file)


@main_bp.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    """Download a PDF file."""
    file = File.query.get_or_404(file_id)

    # Check access
    if not current_user.has_access_to(file):
        abort(403)

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.file_path)

    if not os.path.exists(file_path):
        abort(404)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=file.original_filename
    )


@main_bp.route('/preview/<int:file_id>')
@login_required
def preview_file(file_id):
    """Preview PDF file in browser."""
    file = File.query.get_or_404(file_id)

    # Check access
    if not current_user.has_access_to(file):
        abort(403)

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.file_path)

    if not os.path.exists(file_path):
        abort(404)

    return send_file(
        file_path,
        mimetype='application/pdf'
    )
