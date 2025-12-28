from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model for authentication and access control."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
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
