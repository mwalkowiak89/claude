import logging
from flask import current_app, render_template, url_for
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


def send_file_update_notification(file, users):
    """Send notification about file update to all users with access."""
    if not users:
        return

    recipient_emails = [user.email for user in users]

    subject = f'[PDF Manager] Zaktualizowano plik: {file.filename}'

    text_body = f'''Witaj,

Plik "{file.filename}" został zaktualizowany do wersji {file.version}.

{f"Opis zmian: {file.description}" if file.description else ""}

Zaloguj się do systemu, aby pobrać najnowszą wersję.

Pozdrawiamy,
Zespół PDF Manager
'''

    html_body = f'''
<html>
<body>
    <h2>Aktualizacja pliku</h2>
    <p>Witaj,</p>
    <p>Plik <strong>"{file.filename}"</strong> został zaktualizowany do wersji <strong>{file.version}</strong>.</p>
    {f"<p><em>Opis zmian:</em> {file.description}</p>" if file.description else ""}
    <p>Zaloguj się do systemu, aby pobrać najnowszą wersję.</p>
    <hr>
    <p>Pozdrawiamy,<br>Zespół PDF Manager</p>
</body>
</html>
'''

    for email in recipient_emails:
        send_email(subject, [email], text_body, html_body)


def send_new_access_notification(user, files_list, login_url=None):
    """
    Send notification about new file access to a user.

    Args:
        user: User object who received access
        files_list: List of File objects the user now has access to
        login_url: Optional login URL (will be generated if not provided)

    Returns:
        bool: True if email was queued, False if skipped
    """
    if not files_list:
        return False

    if not is_mail_configured():
        logger.warning(f'Mail not configured. Skipping notification to {user.email}')
        return False

    # Build file list for email
    file_names = [f.filename for f in files_list]

    subject = 'Otrzymałeś dostęp do nowych plików w PDF Manager'

    # Build text version
    files_text = ""
    for f in files_list:
        files_text += f"\n- {f.filename} - wersja {f.version}"
        if f.description:
            files_text += f"\n  Opis: {f.description}"
        files_text += "\n"

    text_body = f'''Witaj,

Otrzymałeś dostęp do następujących plików:
{files_text}
Zaloguj się aby je pobrać: {login_url or '[link do systemu]'}

---
Pozdrawienia,
PDF Manager
'''

    # Build HTML version
    files_html = ""
    for f in files_list:
        files_html += f'''
        <li style="margin-bottom: 15px;">
            <strong style="color: #dc3545;">📄 {f.filename}</strong> - wersja {f.version}
            {f'<br><span style="color: #6c757d; font-size: 0.9em;">Opis: {f.description}</span>' if f.description else ''}
        </li>'''

    html_body = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
        <h1 style="margin: 0; font-size: 24px;">📁 Nowy dostęp do plików</h1>
    </div>

    <div style="background: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; border-top: none;">
        <p>Witaj,</p>

        <p>Otrzymałeś dostęp do następujących plików:</p>

        <ul style="background: white; padding: 20px 20px 20px 40px; border-radius: 8px; border: 1px solid #dee2e6;">
            {files_html}
        </ul>

        <div style="text-align: center; margin: 25px 0;">
            <a href="{login_url or '#'}"
               style="display: inline-block; background: #0d6efd; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                Zaloguj się i pobierz pliki
            </a>
        </div>
    </div>

    <div style="background: #e9ecef; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 0.9em; color: #6c757d;">
        <p style="margin: 0;">Pozdrawienia,<br><strong>PDF Manager</strong></p>
    </div>
</body>
</html>
'''

    # Create and send message
    try:
        msg = Message(
            subject=subject,
            recipients=[user.email],
            body=text_body,
            html=html_body
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
