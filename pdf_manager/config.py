import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload settings
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max file size
    ALLOWED_EXTENSIONS = {'pdf'}

    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 'yes']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@pdfmanager.com')

    # Rate limiting settings
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_DEFAULT = "200 per day, 100 per hour"
    RATELIMIT_HEADERS_ENABLED = True
    # IPs that are exempt from rate limiting (localhost for development)
    RATELIMIT_WHITELIST = os.environ.get('RATELIMIT_WHITELIST', '').split(',') if os.environ.get('RATELIMIT_WHITELIST') else []

    # Babel / Internationalization settings
    BABEL_DEFAULT_LOCALE = 'pl'
    BABEL_SUPPORTED_LOCALES = ['pl', 'en', 'de', 'pt', 'fr', 'es']
    LANGUAGES = {
        'pl': {'name': 'Polski', 'flag': '🇵🇱'},
        'en': {'name': 'English', 'flag': '🇬🇧'},
        'de': {'name': 'Deutsch', 'flag': '🇩🇪'},
        'pt': {'name': 'Português', 'flag': '🇵🇹'},
        'fr': {'name': 'Français', 'flag': '🇫🇷'},
        'es': {'name': 'Español', 'flag': '🇪🇸'}
    }
