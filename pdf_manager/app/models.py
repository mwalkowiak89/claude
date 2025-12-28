from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Available languages
LANGUAGES = [
    ('pl', 'Polski'),
    ('en', 'English'),
    ('de', 'Deutsch'),
    ('pt', 'Português'),
    ('fr', 'Français'),
    ('es', 'Español')
]

LANGUAGE_CODES = [code for code, name in LANGUAGES]

# Email template types
TEMPLATE_TYPES = [
    ('new_access', 'Nowy dostęp do plików'),
    ('file_update', 'Aktualizacja pliku')
]


class User(UserMixin, db.Model):
    """User model for authentication and access control."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    preferred_language = db.Column(db.String(5), default='pl', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to files through access table
    accessible_files = db.relationship(
        'File',
        secondary='user_file_access',
        back_populates='authorized_users',
        lazy='dynamic'
    )

    def set_password(self, password):
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the user's password."""
        return check_password_hash(self.password_hash, password)

    def has_access_to(self, file):
        """Check if user has access to a specific file."""
        if self.is_admin:
            return True
        return UserFileAccess.query.filter_by(
            user_id=self.id,
            file_id=file.id
        ).first() is not None

    def get_language_name(self):
        """Get the display name for user's preferred language."""
        for code, name in LANGUAGES:
            if code == self.preferred_language:
                return name
        return 'Polski'

    def __repr__(self):
        return f'<User {self.email}>'


class File(db.Model):
    """PDF file model with versioning."""
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    description = db.Column(db.Text)

    # Relationship to users through access table
    authorized_users = db.relationship(
        'User',
        secondary='user_file_access',
        back_populates='accessible_files',
        lazy='dynamic'
    )

    def get_users_with_access(self):
        """Get all users who have access to this file."""
        return User.query.join(UserFileAccess).filter(
            UserFileAccess.file_id == self.id
        ).all()

    def __repr__(self):
        return f'<File {self.filename} v{self.version}>'


class UserFileAccess(db.Model):
    """Association table for user-file access permissions."""
    __tablename__ = 'user_file_access'

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        primary_key=True
    )
    file_id = db.Column(
        db.Integer,
        db.ForeignKey('files.id', ondelete='CASCADE'),
        primary_key=True
    )
    granted_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships for easier querying
    user = db.relationship('User', backref=db.backref('file_access', lazy='dynamic'))
    file = db.relationship('File', backref=db.backref('user_access', lazy='dynamic'))

    def __repr__(self):
        return f'<Access user={self.user_id} file={self.file_id}>'


class EmailTemplate(db.Model):
    """Email templates with multi-language support."""
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    template_type = db.Column(db.String(50), nullable=False, index=True)
    language = db.Column(db.String(5), nullable=False, index=True)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    variables = db.Column(db.Text)  # JSON or comma-separated list of available variables
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: one template per type+language
    __table_args__ = (
        db.UniqueConstraint('template_type', 'language', name='uq_template_type_language'),
    )

    @staticmethod
    def get_template(template_type, language, fallback_languages=None):
        """
        Get email template by type and language with fallback.

        Args:
            template_type: Type of template ('new_access', 'file_update')
            language: Preferred language code
            fallback_languages: List of fallback languages (default: ['en', 'pl'])

        Returns:
            EmailTemplate or None
        """
        if fallback_languages is None:
            fallback_languages = ['en', 'pl']

        # Try preferred language first
        template = EmailTemplate.query.filter_by(
            template_type=template_type,
            language=language
        ).first()

        if template:
            return template

        # Try fallback languages
        for fallback_lang in fallback_languages:
            if fallback_lang != language:
                template = EmailTemplate.query.filter_by(
                    template_type=template_type,
                    language=fallback_lang
                ).first()
                if template:
                    return template

        return None

    def render(self, context):
        """
        Render template with given context.

        Args:
            context: Dict with variable values, e.g.:
                     {'user_name': 'Jan', 'file_list': '<ul>...</ul>', 'login_url': 'http://...'}

        Returns:
            Tuple of (subject, body) with variables replaced
        """
        subject = self.subject
        body = self.body

        for key, value in context.items():
            placeholder = '{' + key + '}'
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        return subject, body

    def get_type_display(self):
        """Get display name for template type."""
        for code, name in TEMPLATE_TYPES:
            if code == self.template_type:
                return name
        return self.template_type

    def get_language_display(self):
        """Get display name for language."""
        for code, name in LANGUAGES:
            if code == self.language:
                return name
        return self.language

    def __repr__(self):
        return f'<EmailTemplate {self.template_type}:{self.language}>'


def seed_email_templates():
    """Create default email templates if they don't exist."""
    templates = [
        # Polish - New Access
        {
            'template_type': 'new_access',
            'language': 'pl',
            'subject': 'Nowy dostęp do plików - PDF Manager',
            'body': '''<p>Witaj {user_name},</p>

<p>Otrzymałeś dostęp do następujących plików ({file_count}):</p>

{file_list}

<p>Zaloguj się aby je pobrać: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Pozdrawienia,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_list}, {file_count}, {login_url}'
        },
        # English - New Access
        {
            'template_type': 'new_access',
            'language': 'en',
            'subject': 'New file access - PDF Manager',
            'body': '''<p>Hello {user_name},</p>

<p>You have been granted access to the following files ({file_count}):</p>

{file_list}

<p>Login here: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Best regards,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_list}, {file_count}, {login_url}'
        },
        # German - New Access
        {
            'template_type': 'new_access',
            'language': 'de',
            'subject': 'Neuer Dateizugriff - PDF Manager',
            'body': '''<p>Hallo {user_name},</p>

<p>Sie haben Zugriff auf die folgenden Dateien erhalten ({file_count}):</p>

{file_list}

<p>Hier einloggen: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Mit freundlichen Grüßen,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_list}, {file_count}, {login_url}'
        },
        # Portuguese - New Access
        {
            'template_type': 'new_access',
            'language': 'pt',
            'subject': 'Novo acesso a arquivos - PDF Manager',
            'body': '''<p>Olá {user_name},</p>

<p>Você recebeu acesso aos seguintes arquivos ({file_count}):</p>

{file_list}

<p>Faça login aqui: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Atenciosamente,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_list}, {file_count}, {login_url}'
        },
        # French - New Access
        {
            'template_type': 'new_access',
            'language': 'fr',
            'subject': 'Nouvel accès aux fichiers - PDF Manager',
            'body': '''<p>Bonjour {user_name},</p>

<p>Vous avez reçu l'accès aux fichiers suivants ({file_count}):</p>

{file_list}

<p>Connectez-vous ici: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Cordialement,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_list}, {file_count}, {login_url}'
        },
        # Spanish - New Access
        {
            'template_type': 'new_access',
            'language': 'es',
            'subject': 'Nuevo acceso a archivos - PDF Manager',
            'body': '''<p>Hola {user_name},</p>

<p>Se le ha concedido acceso a los siguientes archivos ({file_count}):</p>

{file_list}

<p>Inicie sesión aquí: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Saludos cordiales,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_list}, {file_count}, {login_url}'
        },
        # Polish - File Update
        {
            'template_type': 'file_update',
            'language': 'pl',
            'subject': 'Aktualizacja pliku: {file_name} - PDF Manager',
            'body': '''<p>Witaj {user_name},</p>

<p>Plik <strong>{file_name}</strong> został zaktualizowany do wersji <strong>{file_version}</strong>.</p>

{file_description}

<p>Zaloguj się aby pobrać nową wersję: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Pozdrawienia,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_name}, {file_version}, {file_description}, {login_url}'
        },
        # English - File Update
        {
            'template_type': 'file_update',
            'language': 'en',
            'subject': 'File updated: {file_name} - PDF Manager',
            'body': '''<p>Hello {user_name},</p>

<p>The file <strong>{file_name}</strong> has been updated to version <strong>{file_version}</strong>.</p>

{file_description}

<p>Login to download the new version: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Best regards,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_name}, {file_version}, {file_description}, {login_url}'
        },
        # German - File Update
        {
            'template_type': 'file_update',
            'language': 'de',
            'subject': 'Datei aktualisiert: {file_name} - PDF Manager',
            'body': '''<p>Hallo {user_name},</p>

<p>Die Datei <strong>{file_name}</strong> wurde auf Version <strong>{file_version}</strong> aktualisiert.</p>

{file_description}

<p>Melden Sie sich an, um die neue Version herunterzuladen: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Mit freundlichen Grüßen,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_name}, {file_version}, {file_description}, {login_url}'
        },
        # Portuguese - File Update
        {
            'template_type': 'file_update',
            'language': 'pt',
            'subject': 'Arquivo atualizado: {file_name} - PDF Manager',
            'body': '''<p>Olá {user_name},</p>

<p>O arquivo <strong>{file_name}</strong> foi atualizado para a versão <strong>{file_version}</strong>.</p>

{file_description}

<p>Faça login para baixar a nova versão: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Atenciosamente,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_name}, {file_version}, {file_description}, {login_url}'
        },
        # French - File Update
        {
            'template_type': 'file_update',
            'language': 'fr',
            'subject': 'Fichier mis à jour: {file_name} - PDF Manager',
            'body': '''<p>Bonjour {user_name},</p>

<p>Le fichier <strong>{file_name}</strong> a été mis à jour vers la version <strong>{file_version}</strong>.</p>

{file_description}

<p>Connectez-vous pour télécharger la nouvelle version: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Cordialement,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_name}, {file_version}, {file_description}, {login_url}'
        },
        # Spanish - File Update
        {
            'template_type': 'file_update',
            'language': 'es',
            'subject': 'Archivo actualizado: {file_name} - PDF Manager',
            'body': '''<p>Hola {user_name},</p>

<p>El archivo <strong>{file_name}</strong> ha sido actualizado a la versión <strong>{file_version}</strong>.</p>

{file_description}

<p>Inicie sesión para descargar la nueva versión: <a href="{login_url}">{login_url}</a></p>

<hr>
<p>Saludos cordiales,<br><strong>PDF Manager</strong></p>''',
            'variables': '{user_name}, {file_name}, {file_version}, {file_description}, {login_url}'
        },
    ]

    for template_data in templates:
        existing = EmailTemplate.query.filter_by(
            template_type=template_data['template_type'],
            language=template_data['language']
        ).first()

        if not existing:
            template = EmailTemplate(**template_data)
            db.session.add(template)

    db.session.commit()
