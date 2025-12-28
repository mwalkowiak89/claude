from flask import current_app, render_template
from flask_mail import Mail, Message
from threading import Thread

mail = Mail()


def send_async_email(app, msg):
    """Send email asynchronously."""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f'Failed to send email: {e}')


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
