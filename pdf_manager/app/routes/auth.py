import io
import base64
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
import qrcode
from app.models import db, User
from app.forms import LoginForm, TwoFactorVerifyForm, TwoFactorSetupForm, TwoFactorDisableForm
from app import limiter

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", error_message="Zbyt wiele prób logowania. Spróbuj za minutę.")
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        # Check if admin needs 2FA setup
        if current_user.requires_2fa_setup():
            return redirect(url_for('auth.setup_2fa'))
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()

        if user is None or not user.check_password(form.password.data):
            flash('Nieprawidłowy email lub hasło.', 'danger')
            return redirect(url_for('auth.login'))

        # Check if 2FA is enabled
        if user.otp_enabled:
            # Store user ID in session for 2FA verification
            session['2fa_user_id'] = user.id
            session['2fa_remember'] = form.remember_me.data
            session['2fa_next'] = request.args.get('next')
            return redirect(url_for('auth.verify_2fa'))

        # No 2FA, login directly
        login_user(user, remember=form.remember_me.data)
        flash('Zalogowano pomyślnie!', 'success')

        # Check if admin needs 2FA setup
        if user.requires_2fa_setup():
            flash('Ze względów bezpieczeństwa, administratorzy muszą włączyć uwierzytelnianie dwuskładnikowe.', 'warning')
            return redirect(url_for('auth.setup_2fa'))

        # Handle redirect after login
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.index')

        return redirect(next_page)

    return render_template('auth/login.html', title='Logowanie', form=form)


@auth_bp.route('/verify-2fa', methods=['GET', 'POST'])
@limiter.limit("5 per minute", error_message="Zbyt wiele prób weryfikacji. Spróbuj za minutę.")
def verify_2fa():
    """Verify 2FA code after password authentication."""
    # Check if we have a pending 2FA verification
    if '2fa_user_id' not in session:
        flash('Sesja wygasła. Zaloguj się ponownie.', 'warning')
        return redirect(url_for('auth.login'))

    user = User.query.get(session['2fa_user_id'])
    if not user:
        session.pop('2fa_user_id', None)
        flash('Użytkownik nie znaleziony.', 'danger')
        return redirect(url_for('auth.login'))

    form = TwoFactorVerifyForm()
    if form.validate_on_submit():
        code = form.code.data.replace(' ', '').replace('-', '')

        # Check if using backup code
        if form.use_backup.data:
            if user.verify_backup_code(code):
                db.session.commit()
                # Clear session data
                remember = session.pop('2fa_remember', False)
                next_page = session.pop('2fa_next', None)
                session.pop('2fa_user_id', None)

                # Login user
                login_user(user, remember=remember)
                flash('Zalogowano przy użyciu kodu zapasowego. Pozostało {} kodów.'.format(
                    user.get_backup_codes_count()), 'warning')

                if not next_page or urlparse(next_page).netloc != '':
                    next_page = url_for('main.index')
                return redirect(next_page)
            else:
                flash('Nieprawidłowy kod zapasowy.', 'danger')
        else:
            # Verify OTP code
            if user.verify_otp(code):
                # Clear session data
                remember = session.pop('2fa_remember', False)
                next_page = session.pop('2fa_next', None)
                session.pop('2fa_user_id', None)

                # Login user
                login_user(user, remember=remember)
                flash('Zalogowano pomyślnie!', 'success')

                if not next_page or urlparse(next_page).netloc != '':
                    next_page = url_for('main.index')
                return redirect(next_page)
            else:
                flash('Nieprawidłowy kod weryfikacyjny.', 'danger')

    return render_template(
        'auth/verify_2fa.html',
        title='Weryfikacja dwuskładnikowa',
        form=form,
        user_email=user.email
    )


@auth_bp.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    """Set up 2FA for current user."""
    if current_user.otp_enabled:
        flash('2FA jest już włączone.', 'info')
        return redirect(url_for('auth.security_settings'))

    # Generate new secret if not exists
    if not current_user.otp_secret:
        current_user.generate_otp_secret()
        db.session.commit()

    form = TwoFactorSetupForm()
    backup_codes = None

    if form.validate_on_submit():
        code = form.code.data.replace(' ', '')

        if current_user.verify_otp(code):
            # Enable 2FA
            current_user.enable_2fa()
            # Generate backup codes
            backup_codes = current_user.generate_backup_codes()
            db.session.commit()

            flash('Uwierzytelnianie dwuskładnikowe zostało włączone!', 'success')
            # Show backup codes page
            return render_template(
                'auth/backup_codes.html',
                title='Kody zapasowe',
                backup_codes=backup_codes
            )
        else:
            flash('Nieprawidłowy kod. Sprawdź czy czas na urządzeniu jest poprawny.', 'danger')

    # Generate QR code
    otp_uri = current_user.get_otp_uri()
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(otp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render_template(
        'auth/setup_2fa.html',
        title='Włącz 2FA',
        form=form,
        qr_code=qr_code_base64,
        secret=current_user.otp_secret,
        is_required=current_user.is_admin
    )


@auth_bp.route('/security', methods=['GET'])
@login_required
def security_settings():
    """Security settings page."""
    return render_template(
        'auth/security.html',
        title='Bezpieczeństwo',
        backup_codes_count=current_user.get_backup_codes_count()
    )


@auth_bp.route('/disable-2fa', methods=['GET', 'POST'])
@login_required
def disable_2fa():
    """Disable 2FA for current user."""
    if not current_user.otp_enabled:
        flash('2FA nie jest włączone.', 'info')
        return redirect(url_for('auth.security_settings'))

    # Admins cannot disable 2FA
    if current_user.is_admin:
        flash('Administratorzy nie mogą wyłączyć uwierzytelniania dwuskładnikowego.', 'danger')
        return redirect(url_for('auth.security_settings'))

    form = TwoFactorDisableForm()

    if form.validate_on_submit():
        # Verify password
        if not current_user.check_password(form.password.data):
            flash('Nieprawidłowe hasło.', 'danger')
            return render_template('auth/disable_2fa.html', title='Wyłącz 2FA', form=form)

        # Verify OTP code
        code = form.code.data.replace(' ', '')
        if not current_user.verify_otp(code):
            flash('Nieprawidłowy kod weryfikacyjny.', 'danger')
            return render_template('auth/disable_2fa.html', title='Wyłącz 2FA', form=form)

        # Disable 2FA
        current_user.disable_2fa()
        db.session.commit()

        flash('Uwierzytelnianie dwuskładnikowe zostało wyłączone.', 'success')
        return redirect(url_for('auth.security_settings'))

    return render_template('auth/disable_2fa.html', title='Wyłącz 2FA', form=form)


@auth_bp.route('/regenerate-backup-codes', methods=['POST'])
@login_required
def regenerate_backup_codes():
    """Regenerate backup codes."""
    if not current_user.otp_enabled:
        flash('2FA nie jest włączone.', 'warning')
        return redirect(url_for('auth.security_settings'))

    backup_codes = current_user.generate_backup_codes()
    db.session.commit()

    flash('Wygenerowano nowe kody zapasowe.', 'success')
    return render_template(
        'auth/backup_codes.html',
        title='Nowe kody zapasowe',
        backup_codes=backup_codes
    )


@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    # Clear any 2FA session data
    session.pop('2fa_user_id', None)
    session.pop('2fa_remember', None)
    session.pop('2fa_next', None)
    flash('Wylogowano pomyślnie.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/cancel-2fa-login')
def cancel_2fa_login():
    """Cancel 2FA login and return to login page."""
    session.pop('2fa_user_id', None)
    session.pop('2fa_remember', None)
    session.pop('2fa_next', None)
    return redirect(url_for('auth.login'))
