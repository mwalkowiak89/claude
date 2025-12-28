import os
import logging
from datetime import datetime
from flask import Flask, request, redirect, url_for
from flask_login import LoginManager, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from app.models import db, User, seed_email_templates
from app.email import mail

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Zaloguj się, aby uzyskać dostęp do tej strony.'
login_manager.login_message_category = 'info'

# Initialize limiter (will be configured in create_app)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "100 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))


def create_app(config_class=Config):
    """Application factory for creating Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    # Initialize rate limiter
    limiter.init_app(app)

    # Configure limiter whitelist (exempt IPs)
    whitelist = app.config.get('RATELIMIT_WHITELIST', [])
    if whitelist:
        @limiter.request_filter
        def ip_whitelist():
            return request.remote_addr in whitelist

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # Context processor for templates
    @app.context_processor
    def utility_processor():
        return {'now': datetime.utcnow}

    # Enforce 2FA setup for admins
    @app.before_request
    def enforce_2fa_for_admins():
        # Skip for static files and certain endpoints
        if request.endpoint and request.endpoint.startswith('static'):
            return None

        # Allow these endpoints without 2FA enforcement
        allowed_endpoints = [
            'auth.setup_2fa',
            'auth.logout',
            'auth.login',
            'auth.verify_2fa',
            'auth.cancel_2fa_login'
        ]

        if request.endpoint in allowed_endpoints:
            return None

        # Check if logged in admin needs to set up 2FA
        if current_user.is_authenticated and current_user.requires_2fa_setup():
            return redirect(url_for('auth.setup_2fa'))

    # Create database tables
    with app.app_context():
        db.create_all()
        # Create default admin if no users exist
        if User.query.count() == 0:
            admin = User(
                email='admin@example.com',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('Created default admin user: admin@example.com / admin123')

        # Seed default email templates
        seed_email_templates()

    # Error handlers
    @app.errorhandler(403)
    def forbidden(error):
        from flask import render_template
        return render_template('errors/403.html', title='Brak dostępu'), 403

    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('errors/404.html', title='Nie znaleziono'), 404

    @app.errorhandler(429)
    def ratelimit_handler(error):
        from flask import render_template, jsonify
        ip = request.remote_addr
        logger.warning(f'Rate limit exceeded for IP: {ip} on {request.path}')

        # Check if request expects JSON
        if request.is_json or request.headers.get('Accept') == 'application/json':
            return jsonify({
                'error': 'Too Many Requests',
                'message': f'Zbyt wiele prób. Spróbuj za chwilę.',
                'retry_after': error.description
            }), 429

        return render_template('errors/429.html', title='Zbyt wiele żądań', error=error), 429

    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        return render_template('errors/500.html', title='Błąd serwera'), 500

    return app
