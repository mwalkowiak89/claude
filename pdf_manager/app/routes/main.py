import os
from flask import Blueprint, render_template, send_file, abort, current_app, redirect, request, session, make_response, flash, url_for, after_this_request
from flask_login import login_required, current_user
from app.models import db, File, UserFileAccess, FileDownload, AppSettings
from app.forms import TermsAcceptanceForm
from app.utils import add_watermark_to_pdf, generate_download_id, check_suspicious_activity, send_suspicious_activity_alert, cleanup_temp_file
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
    """Download a PDF file with watermark."""
    file = File.query.get_or_404(file_id)

    # Check access
    if not current_user.has_access_to(file):
        abort(403)

    # Check if user has accepted terms
    if not current_user.has_accepted_terms():
        flash('Musisz zaakceptować regulamin przed pobraniem plików.', 'warning')
        return redirect(url_for('main.accept_terms', next=url_for('main.download_file', file_id=file_id)))

    # Check download limit (10 downloads per file per user)
    download_count = FileDownload.get_user_download_count(current_user.id, file_id)
    if download_count >= 10:
        flash('Przekroczono limit pobrań dla tego pliku (max 10). Skontaktuj się z administratorem.', 'warning')
        return redirect(url_for('main.index'))

    # Check for suspicious activity
    if check_suspicious_activity(current_user.id, file_id, threshold=5, hours=1):
        flash('Wykryto podejrzaną aktywność. Twoje działania są monitorowane.', 'warning')
        send_suspicious_activity_alert(current_user, file, FileDownload.get_recent_downloads(current_user.id, file_id, 1))

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.file_path)

    if not os.path.exists(file_path):
        abort(404)

    # Generate unique download ID
    download_id = generate_download_id()

    # Log the download
    download_log = FileDownload(
        user_id=current_user.id,
        file_id=file_id,
        download_id=download_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:512] if request.user_agent.string else None
    )
    db.session.add(download_log)
    db.session.commit()

    # Get app name for watermark
    settings = AppSettings.get_settings()
    app_name = settings.app_name if settings.enable_custom_branding else 'PDF Manager'

    # Create temp directory if not exists
    temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp')
    os.makedirs(temp_dir, exist_ok=True)

    # Add watermark to PDF
    watermarked_path = os.path.join(temp_dir, f'{download_id}_{file.original_filename}')

    try:
        add_watermark_to_pdf(
            file_path,
            watermarked_path,
            current_user.email,
            download_id,
            app_name
        )
    except Exception as e:
        # If watermarking fails, serve original file
        current_app.logger.error(f"Watermarking failed: {e}")
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file.original_filename
        )

    # Cleanup temp file after sending
    @after_this_request
    def cleanup(response):
        cleanup_temp_file(watermarked_path)
        return response

    return send_file(
        watermarked_path,
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


@main_bp.route('/accept-terms', methods=['GET', 'POST'])
@login_required
def accept_terms():
    """Accept terms of use before downloading files."""
    if current_user.has_accepted_terms():
        next_url = request.args.get('next', url_for('main.index'))
        return redirect(next_url)

    form = TermsAcceptanceForm()

    if form.validate_on_submit():
        current_user.accept_terms()
        db.session.commit()
        flash('Dziękujemy za zaakceptowanie regulaminu.', 'success')
        next_url = request.args.get('next', url_for('main.index'))
        return redirect(next_url)

    return render_template(
        'main/accept_terms.html',
        title='Akceptacja regulaminu',
        form=form
    )
