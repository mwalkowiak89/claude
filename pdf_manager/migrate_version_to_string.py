#!/usr/bin/env python3
"""
Migration script to convert File.version from Integer to String.

Usage:
    python migrate_version_to_string.py

This script:
1. Creates a new files table with version as String
2. Copies all data, converting integer versions to strings
3. Drops the old table
4. Renames the new table

Backup your database before running this script!
"""

import os
import sys
import sqlite3
from datetime import datetime

# Get the database path from config
DATABASE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'instance',
    'app.db'
)


def migrate():
    """Perform the migration."""
    if not os.path.exists(DATABASE_PATH):
        print(f"Database not found at {DATABASE_PATH}")
        print("If this is a new installation, no migration is needed.")
        sys.exit(0)

    # Create backup
    backup_path = DATABASE_PATH + f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"Creating backup at {backup_path}")

    import shutil
    shutil.copy2(DATABASE_PATH, backup_path)
    print("Backup created successfully.")

    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Check current column type
        cursor.execute("PRAGMA table_info(files)")
        columns = cursor.fetchall()
        version_col = next((c for c in columns if c[1] == 'version'), None)

        if version_col is None:
            print("No 'version' column found in 'files' table.")
            sys.exit(1)

        # Column info: (cid, name, type, notnull, default, pk)
        current_type = version_col[2].upper()
        print(f"Current 'version' column type: {current_type}")

        if 'VARCHAR' in current_type or 'TEXT' in current_type or 'STRING' in current_type:
            print("Column is already a string type. No migration needed.")
            conn.close()
            sys.exit(0)

        print("Starting migration: INTEGER -> VARCHAR(50)")

        # Step 1: Create new table with correct schema
        cursor.execute("""
            CREATE TABLE files_new (
                id INTEGER PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                original_filename VARCHAR(255) NOT NULL,
                version VARCHAR(50) NOT NULL DEFAULT '1',
                upload_date DATETIME NOT NULL,
                file_path VARCHAR(512) NOT NULL,
                description TEXT
            )
        """)

        # Step 2: Copy data, converting version to string
        cursor.execute("""
            INSERT INTO files_new (id, filename, original_filename, version, upload_date, file_path, description)
            SELECT id, filename, original_filename, CAST(version AS TEXT), upload_date, file_path, description
            FROM files
        """)

        # Step 3: Drop old table
        cursor.execute("DROP TABLE files")

        # Step 4: Rename new table
        cursor.execute("ALTER TABLE files_new RENAME TO files")

        # Commit changes
        conn.commit()
        print("Migration completed successfully!")
        print(f"Backup saved at: {backup_path}")

    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        print(f"Database rolled back. Backup available at: {backup_path}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    print("=" * 50)
    print("File Version Migration: Integer -> String")
    print("=" * 50)
    migrate()
