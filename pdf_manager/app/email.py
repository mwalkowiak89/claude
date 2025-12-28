import logging
from flask import current_app, url_for
from flask_mail import Mail, Message
from threading import Thread

mail = Mail()
logger = logging.getLogger(__name__)


def is_mail_configured():
    """Check if mail server is properly configured."""
    return bool(current_app.config.get('MAIL_SERVER')) and bool(current_app.config.get('MAIL_USERNAME'))


def send_async_email(app, msg, user_email=None, file_names=None):
    """Send email asynchronously."""
    with app.app_context():
        try:
            mail.send(msg)
            if user_email and file_names:
                logger.info(f'Email sent to {user_email} for files: {", ".join(file_names)}')
        except Exception as e:
            logger.error(f'Failed to send email to {user_email}: {e}')


def send_email(subject, recipients, text_body, html_body=None):
    """Send an email."""
    msg = Message(
        subject=subject,
        recipients=recipients,
        body=text_body,
        html=html_body
    )

    # Send asynchronously to avoid blocking
    Thread(
        target=send_async_email,
        args=(current_app._get_current_object(), msg)
    ).start()


def build_file_list_html(files):
    """Build HTML file list for email templates."""
    file_list_html = '<ul style="list-style: none; padding: 0; margin: 15px 0;">'
    for f in files:
        desc_html = ''
        if f.description:
            desc_html = f'<br><span style="color: #6c757d; font-size: 0.9em;">Opis: {f.description}</span>'
        file_list_html += f'''<li style="margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
            <strong style="color: #dc3545;">📄 {f.filename}</strong>
            <span style="color: #6c757d;"> (v{f.version})</span>
            {desc_html}
        </li>'''
    file_list_html += '</ul>'
    return file_list_html


def build_text_file_list(files):
    """Build plain text file list for email templates."""
    text_list = ""
    for f in files:
        text_list += f"\n- {f.filename} (v{f.version})"
        if f.description:
            text_list += f"\n  Opis: {f.description}"
    return text_list


def send_file_update_notification(file, users, login_url=None):
    """
    Send notification about file update to all users with access.
    Uses email templates with user's preferred language.
    """
    from app.models import EmailTemplate

    if not users:
        return

    if not is_mail_configured():
        logger.warning('Mail not configured. Skipping file update notifications.')
        return

    if not login_url:
        try:
            login_url = url_for('auth.login', _external=True)
        except RuntimeError:
            login_url = '[link do systemu]'

    for user in users:
        # Get template for user's preferred language
        template = EmailTemplate.get_template('file_update', user.preferred_language)

        if not template:
            logger.warning(f'No file_update template found for language {user.preferred_language}')
            continue

        # Prepare context
        description_html = ''
        if file.description:
            description_html = f'<p><em>Opis zmian:</em> {file.description}</p>'

        context = {
            'user_name': user.email,
            'file_name': file.filename,
            'file_version': str(file.version),
            'file_description': description_html,
            'login_url': login_url
        }

        # Render template
        subject, html_body = template.render(context)

        # Build plain text version
        text_body = f'''Plik "{file.filename}" został zaktualizowany do wersji {file.version}.

{f"Opis zmian: {file.description}" if file.description else ""}

Zaloguj się aby pobrać nową wersję: {login_url}

---
PDF Manager'''

        # Send email
        try:
            msg = Message(
                subject=subject,
                recipients=[user.email],
                body=text_body,
                html=html_body
            )

            Thread(
                target=send_async_email,
                args=(current_app._get_current_object(), msg, user.email, [file.filename])
            ).start()

        except Exception as e:
            logger.error(f'Failed to create email for {user.email}: {e}')


def send_new_access_notification(user, files_list, login_url=None):
    """
    Send notification about new file access to a user.
    Uses email templates with user's preferred language.

    Args:
        user: User object who received access
        files_list: List of File objects the user now has access to
        login_url: Optional login URL (will be generated if not provided)

    Returns:
        bool: True if email was queued, False if skipped
    """
    from app.models import EmailTemplate

    if not files_list:
        return False

    if not is_mail_configured():
        logger.warning(f'Mail not configured. Skipping notification to {user.email}')
        return False

    # Get template for user's preferred language
    template = EmailTemplate.get_template('new_access', user.preferred_language)

    if not template:
        logger.warning(f'No new_access template found for language {user.preferred_language}')
        return False

    # Build file list HTML
    file_list_html = build_file_list_html(files_list)
    file_names = [f.filename for f in files_list]

    # Prepare context
    context = {
        'user_name': user.email,
        'file_list': file_list_html,
        'file_count': str(len(files_list)),
        'login_url': login_url or '[link do systemu]'
    }

    # Render template
    subject, html_body = template.render(context)

    # Wrap body in nice HTML structure
    full_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
        <h1 style="margin: 0; font-size: 24px;">📁 PDF Manager</h1>
    </div>

    <div style="background: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; border-top: none;">
        {html_body}

        <div style="text-align: center; margin: 25px 0;">
            <a href="{login_url or '#'}"
               style="display: inline-block; background: #0d6efd; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                Zaloguj się i pobierz pliki
            </a>
        </div>
    </div>

    <div style="background: #e9ecef; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 0.9em; color: #6c757d;">
        <p style="margin: 0;">PDF Manager</p>
    </div>
</body>
</html>'''

    # Build text version
    text_body = f'''Witaj,

Otrzymałeś dostęp do następujących plików ({len(files_list)}):
{build_text_file_list(files_list)}

Zaloguj się aby je pobrać: {login_url or '[link do systemu]'}

---
PDF Manager'''

    # Create and send message
    try:
        msg = Message(
            subject=subject,
            recipients=[user.email],
            body=text_body,
            html=full_html
        )

        Thread(
            target=send_async_email,
            args=(current_app._get_current_object(), msg, user.email, file_names)
        ).start()

        return True

    except Exception as e:
        logger.error(f'Failed to create email for {user.email}: {e}')
        return False


def send_bulk_access_notifications(access_map, login_url=None):
    """
    Send notifications to multiple users about their new file access.

    Args:
        access_map: Dict mapping User objects to lists of File objects
                   {user1: [file1, file2], user2: [file3]}
        login_url: Optional login URL

    Returns:
        int: Number of users who were sent notifications
    """
    if not access_map:
        return 0

    if not is_mail_configured():
        logger.warning('Mail not configured. Skipping all access notifications.')
        return 0

    sent_count = 0
    for user, files in access_map.items():
        if files and send_new_access_notification(user, files, login_url):
            sent_count += 1

    return sent_count
