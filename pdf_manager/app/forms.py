from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, TextAreaField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models import User


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
