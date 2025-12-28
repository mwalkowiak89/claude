import os
from datetime import datetime
from flask import Flask
from flask_login import LoginManager
from config import Config
from app.models import db, User, seed_email_templates
from app.email import mail

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Zaloguj się, aby uzyskać dostęp do tej strony.'
login_manager.login_message_category = 'info'


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

    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        return render_template('errors/500.html', title='Błąd serwera'), 500

    return app
