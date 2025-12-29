import os
from flask import Blueprint, render_template, send_file, abort, current_app, redirect, request, session, make_response
from flask_login import login_required, current_user
from app.models import File, UserFileAccess
from app import limiter

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
@limiter.limit("60 per minute")
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
@limiter.limit("60 per minute")
def view_file(file_id):
    """View file details."""
    file = File.query.get_or_404(file_id)

    # Check access
    if not current_user.has_access_to(file):
        abort(403)

    return render_template('main/file_view.html', title=file.filename, file=file)


@main_bp.route('/download/<int:file_id>')
@login_required
@limiter.limit("50 per hour", error_message="Przekroczono limit pobrań. Spróbuj za godzinę.")
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
@limiter.limit("100 per hour")
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


@main_bp.route('/set-language/<language>')
def set_language(language):
    """Set the user's preferred language."""
    supported_languages = current_app.config.get('BABEL_SUPPORTED_LOCALES', ['pl', 'en', 'de', 'pt', 'fr', 'es'])

    if language not in supported_languages:
        language = 'pl'

    # Store in session
    session['language'] = language

    # Get the redirect URL (referrer or index)
    next_page = request.referrer or '/'

    # Create response with redirect
    response = make_response(redirect(next_page))

    # Also set a cookie for non-authenticated users (30 days)
    response.set_cookie('language', language, max_age=30*24*60*60, samesite='Lax')

    return response
