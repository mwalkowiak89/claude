#!/usr/bin/env python3
"""
Backup script for PDF Manager application.
Creates compressed backups of database and uploaded files.

Usage:
    python backup.py

Cron example (daily at 2:00 AM):
    0 2 * * * cd /path/to/project && /path/to/venv/bin/python backup.py >> backups/backup.log 2>&1
"""

import os
import sys
import zipfile
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BACKUP_DIR = Path('backups')
DAILY_BACKUP_DIR = BACKUP_DIR / 'daily'
DATABASE_FILE = 'app.db'
UPLOADS_DIR = 'uploads'
BACKUP_RETENTION_DAYS = 7


def get_backup_info(backup_path):
    """Get information about a backup file."""
    if not backup_path.exists():
        return None
    
    stat = backup_path.stat()
    size_bytes = stat.st_size
    size_mb = size_bytes / (1024 * 1024)
    created = datetime.fromtimestamp(stat.st_mtime)
    
    # Count files in backup
    file_count = 0
    try:
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            file_count = len(zipf.namelist())
    except:
        pass
    
    return {
        'filename': backup_path.name,
        'path': str(backup_path),
        'size_bytes': size_bytes,
        'size_mb': round(size_mb, 2),
        'created': created,
        'file_count': file_count
    }


def list_backups():
    """List all available backups."""
    backups = []
    
    if not DAILY_BACKUP_DIR.exists():
        return backups
    
    for backup_file in DAILY_BACKUP_DIR.glob('backup_*.zip'):
        info = get_backup_info(backup_file)
        if info:
            backups.append(info)
    
    # Sort by creation date, newest first
    backups.sort(key=lambda x: x['created'], reverse=True)
    return backups


def create_backup(notify_admins=False):
    """
    Creates a backup of the database and uploaded files.
    
    Args:
        notify_admins: If True, send email notification to admins (requires Flask app context)
    
    Returns:
        dict: Backup information or None if failed
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Ensure backup directory exists
    DAILY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Backup filename
    backup_filename = f'backup_{timestamp}.zip'
    backup_path = DAILY_BACKUP_DIR / backup_filename
    
    files_backed_up = 0
    
    try:
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Backup database
            if os.path.exists(DATABASE_FILE):
                zipf.write(DATABASE_FILE, DATABASE_FILE)
                files_backed_up += 1
                logger.info(f'Added database: {DATABASE_FILE}')
            else:
                logger.warning(f'Database file not found: {DATABASE_FILE}')
            
            # Backup uploaded files
            if os.path.exists(UPLOADS_DIR):
                for root, dirs, files in os.walk(UPLOADS_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, '.')
                        zipf.write(file_path, arcname)
                        files_backed_up += 1
                logger.info(f'Added {files_backed_up - 1} files from uploads/')
            else:
                logger.warning(f'Uploads directory not found: {UPLOADS_DIR}')
        
        # Get backup info
        info = get_backup_info(backup_path)
        
        logger.info(f'✓ Backup created: {backup_filename} ({info["size_mb"]:.2f} MB, {files_backed_up} files)')
        
        # Cleanup old backups
        deleted = cleanup_old_backups(DAILY_BACKUP_DIR, days=BACKUP_RETENTION_DAYS)
        if deleted > 0:
            logger.info(f'✓ Cleaned up {deleted} old backup(s)')
        
        # Send email notification if requested
        if notify_admins:
            try:
                send_backup_notification(info, success=True)
            except Exception as e:
                logger.warning(f'Failed to send backup notification: {e}')
        
        return info
        
    except Exception as e:
        logger.error(f'✗ Backup failed: {e}')
        
        # Remove partial backup if exists
        if backup_path.exists():
            backup_path.unlink()
        
        if notify_admins:
            try:
                send_backup_notification(None, success=False, error=str(e))
            except Exception as ne:
                logger.warning(f'Failed to send error notification: {ne}')
        
        raise


def cleanup_old_backups(backup_dir, days=7):
    """
    Remove backups older than specified days.
    
    Args:
        backup_dir: Path to backup directory
        days: Number of days to keep backups
    
    Returns:
        int: Number of deleted backups
    """
    cutoff = datetime.now() - timedelta(days=days)
    deleted = 0
    
    backup_dir = Path(backup_dir)
    if not backup_dir.exists():
        return 0
    
    for backup_file in backup_dir.glob('backup_*.zip'):
        try:
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_time < cutoff:
                backup_file.unlink()
                deleted += 1
                logger.info(f'Deleted old backup: {backup_file.name}')
        except Exception as e:
            logger.warning(f'Failed to delete {backup_file.name}: {e}')
    
    return deleted


def restore_backup(backup_filename):
    """
    Restore database and files from a backup.
    
    Args:
        backup_filename: Name of the backup file to restore
    
    Returns:
        dict: Restore information
    """
    backup_path = DAILY_BACKUP_DIR / backup_filename
    
    if not backup_path.exists():
        raise FileNotFoundError(f'Backup not found: {backup_filename}')
    
    files_restored = 0
    
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        # Extract all files
        for member in zipf.namelist():
            zipf.extract(member, '.')
            files_restored += 1
            logger.info(f'Restored: {member}')
    
    logger.info(f'✓ Restored {files_restored} files from {backup_filename}')
    
    return {
        'filename': backup_filename,
        'files_restored': files_restored
    }


def delete_backup(backup_filename):
    """
    Delete a specific backup file.
    
    Args:
        backup_filename: Name of the backup file to delete
    
    Returns:
        bool: True if deleted successfully
    """
    backup_path = DAILY_BACKUP_DIR / backup_filename
    
    if not backup_path.exists():
        raise FileNotFoundError(f'Backup not found: {backup_filename}')
    
    backup_path.unlink()
    logger.info(f'✓ Deleted backup: {backup_filename}')
    
    return True


def send_backup_notification(backup_info, success=True, error=None):
    """
    Send email notification about backup status to all admins.
    Must be called within Flask application context.
    """
    from flask import current_app
    from app.models import User
    from app.email import send_email
    
    # Get all admin emails
    admins = User.query.filter_by(is_admin=True).all()
    admin_emails = [admin.email for admin in admins]
    
    if not admin_emails:
        return
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    if success and backup_info:
        subject = f'✓ Backup PDF Manager - {today}'
        body = f'''Backup wykonany pomyślnie.

Plik: {backup_info['filename']}
Rozmiar: {backup_info['size_mb']:.2f} MB
Plików: {backup_info['file_count']}
Data: {backup_info['created'].strftime('%Y-%m-%d %H:%M:%S')}

---
PDF Manager - Automatyczny backup
'''
    else:
        subject = f'✗ BŁĄD backupu PDF Manager - {today}'
        body = f'''Backup nie powiódł się!

Błąd: {error or 'Nieznany błąd'}

Sprawdź logi serwera.

---
PDF Manager - Automatyczny backup
'''
    
    for email in admin_emails:
        try:
            send_email(subject, [email], body)
        except Exception as e:
            logger.warning(f'Failed to send notification to {email}: {e}')


def get_backup_path(backup_filename):
    """Get full path to a backup file."""
    return DAILY_BACKUP_DIR / backup_filename


if __name__ == '__main__':
    print('=' * 50)
    print(f'PDF Manager Backup - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 50)
    
    try:
        backup_info = create_backup(notify_admins=False)
        print(f'\n✓ Backup completed successfully!')
        print(f'  File: {backup_info["filename"]}')
        print(f'  Size: {backup_info["size_mb"]:.2f} MB')
        print(f'  Files: {backup_info["file_count"]}')
        sys.exit(0)
    except Exception as e:
        print(f'\n✗ Backup failed: {e}')
        sys.exit(1)
