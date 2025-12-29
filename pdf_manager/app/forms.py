from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, TextAreaField, SubmitField, SelectMultipleField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models import User, LANGUAGES, TEMPLATE_TYPES


class LoginForm(FlaskForm):
    """Login form for user authentication."""
    email = StringField('Email', validators=[
        DataRequired(message='Email jest wymagany'),
        Email(message='Nieprawidłowy format email')
    ])
    password = PasswordField('Hasło', validators=[
        DataRequired(message='Hasło jest wymagane')
    ])
    remember_me = BooleanField('Zapamiętaj mnie')
    submit = SubmitField('Zaloguj się')


class RegistrationForm(FlaskForm):
    """Registration form for new users (admin only)."""
    email = StringField('Email', validators=[
        DataRequired(message='Email jest wymagany'),
        Email(message='Nieprawidłowy format email'),
        Length(max=120)
    ])
    password = PasswordField('Hasło', validators=[
        DataRequired(message='Hasło jest wymagane'),
        Length(min=8, message='Hasło musi mieć minimum 8 znaków')
    ])
    password2 = PasswordField('Potwierdź hasło', validators=[
        DataRequired(message='Potwierdzenie hasła jest wymagane'),
        EqualTo('password', message='Hasła muszą być identyczne')
    ])
    preferred_language = SelectField('Preferowany język', choices=LANGUAGES, default='pl')
    is_admin = BooleanField('Administrator')
    submit = SubmitField('Utwórz konto')

    def validate_email(self, email):
        """Check if email is already registered."""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('Ten adres email jest już zarejestrowany.')


class FileUploadForm(FlaskForm):
    """Form for uploading PDF files."""
    file = FileField('Plik PDF', validators=[
        FileRequired(message='Plik jest wymagany'),
        FileAllowed(['pdf'], message='Dozwolone tylko pliki PDF')
    ])
    description = TextAreaField('Opis', validators=[
        Length(max=500, message='Opis może mieć maksymalnie 500 znaków')
    ])
    submit = SubmitField('Wyślij plik')


class FileUpdateForm(FlaskForm):
    """Form for updating existing PDF file (new version)."""
    file = FileField('Nowa wersja pliku PDF', validators=[
        FileRequired(message='Plik jest wymagany'),
        FileAllowed(['pdf'], message='Dozwolone tylko pliki PDF')
    ])
    description = TextAreaField('Opis zmian', validators=[
        Length(max=500, message='Opis może mieć maksymalnie 500 znaków')
    ])
    submit = SubmitField('Aktualizuj plik')


class FileAccessForm(FlaskForm):
    """Form for managing user access to files."""
    users = SelectMultipleField('Użytkownicy', coerce=int)
    submit = SubmitField('Zapisz uprawnienia')


class EditUserForm(FlaskForm):
    """Form for editing user details."""
    email = StringField('Email', validators=[
        DataRequired(message='Email jest wymagany'),
        Email(message='Nieprawidłowy format email'),
        Length(max=120)
    ])
    preferred_language = SelectField('Preferowany język', choices=LANGUAGES)
    is_admin = BooleanField('Administrator')
    submit = SubmitField('Zapisz zmiany')


class ChangePasswordForm(FlaskForm):
    """Form for changing user password."""
    new_password = PasswordField('Nowe hasło', validators=[
        DataRequired(message='Hasło jest wymagane'),
        Length(min=8, message='Hasło musi mieć minimum 8 znaków')
    ])
    new_password2 = PasswordField('Potwierdź nowe hasło', validators=[
        DataRequired(message='Potwierdzenie hasła jest wymagane'),
        EqualTo('new_password', message='Hasła muszą być identyczne')
    ])
    submit = SubmitField('Zmień hasło')


class EmailTemplateForm(FlaskForm):
    """Form for editing email templates."""
    subject = StringField('Temat', validators=[
        DataRequired(message='Temat jest wymagany'),
        Length(max=255)
    ])
    body = TextAreaField('Treść', validators=[
        DataRequired(message='Treść jest wymagana')
    ])
    submit = SubmitField('Zapisz szablon')


# ===== Two-Factor Authentication Forms =====

class TwoFactorVerifyForm(FlaskForm):
    """Form for verifying 2FA code during login."""
    code = StringField('Kod weryfikacyjny', validators=[
        DataRequired(message='Kod jest wymagany'),
        Length(min=6, max=8, message='Kod musi mieć 6-8 znaków')
    ])
    use_backup = BooleanField('Użyj kodu zapasowego')
    submit = SubmitField('Weryfikuj')


class TwoFactorSetupForm(FlaskForm):
    """Form for setting up 2FA."""
    code = StringField('Kod z aplikacji', validators=[
        DataRequired(message='Kod jest wymagany'),
        Length(min=6, max=6, message='Kod musi mieć 6 cyfr')
    ])
    submit = SubmitField('Włącz 2FA')


class TwoFactorDisableForm(FlaskForm):
    """Form for disabling 2FA."""
    password = PasswordField('Hasło', validators=[
        DataRequired(message='Hasło jest wymagane')
    ])
    code = StringField('Kod z aplikacji', validators=[
        DataRequired(message='Kod jest wymagany'),
        Length(min=6, max=6, message='Kod musi mieć 6 cyfr')
    ])
    submit = SubmitField('Wyłącz 2FA')


# ===== Backup Forms =====

class BackupRestoreForm(FlaskForm):
    """Form for confirming backup restore."""
    password = PasswordField('Hasło administratora', validators=[
        DataRequired(message='Hasło jest wymagane')
    ])
    confirmation = StringField('Wpisz PRZYWRÓĆ aby potwierdzić', validators=[
        DataRequired(message='Potwierdzenie jest wymagane')
    ])
    submit = SubmitField('Przywróć backup')


# ===== Branding Forms =====

class AppSettingsForm(FlaskForm):
    """Form for application branding settings."""
    app_name = StringField('Nazwa aplikacji', validators=[
        DataRequired(message='Nazwa jest wymagana'),
        Length(min=3, max=50, message='Nazwa musi mieć 3-50 znaków')
    ])
    logo = FileField('Logo (PNG/JPG, max 2MB)', validators=[
        FileAllowed(['png', 'jpg', 'jpeg', 'svg'], message='Dozwolone: PNG, JPG, SVG')
    ])
    primary_color = StringField('Kolor główny (przyciski)', validators=[
        DataRequired(message='Kolor jest wymagany'),
        Length(min=7, max=7, message='Format: #RRGGBB')
    ])
    navbar_color = StringField('Kolor navbar', validators=[
        DataRequired(message='Kolor jest wymagany'),
        Length(min=7, max=7, message='Format: #RRGGBB')
    ])
    enable_custom_branding = BooleanField('Włącz niestandardowy branding')
    submit = SubmitField('Zapisz ustawienia')

    def validate_primary_color(self, field):
        """Validate hex color format."""
        from app.utils import validate_hex_color
        if not validate_hex_color(field.data):
            raise ValidationError('Nieprawidłowy format koloru. Użyj #RRGGBB')

    def validate_navbar_color(self, field):
        """Validate hex color format."""
        from app.utils import validate_hex_color
        if not validate_hex_color(field.data):
            raise ValidationError('Nieprawidłowy format koloru. Użyj #RRGGBB')


# ===== Terms of Use Forms =====

class TermsAcceptanceForm(FlaskForm):
    """Form for accepting terms of use."""
    accept_terms = BooleanField(
        'Oświadczam, że pliki pobrane z systemu są wyłącznie do użytku osobistego '
        'i zobowiązuję się nie rozpowszechniać ich bez autoryzacji.',
        validators=[DataRequired(message='Musisz zaakceptować regulamin')]
    )
    submit = SubmitField('Akceptuję regulamin')
