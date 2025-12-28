#!/usr/bin/env python3
"""
PDF Manager - Application Entry Point

Run this file to start the Flask development server:
    python run.py

For production, use a proper WSGI server like Gunicorn:
    gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
"""

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("PDF Manager - System zarządzania dostępem do plików")
    print("=" * 50)
    print("\nDomyślne konto administratora:")
    print("  Email: admin@example.com")
    print("  Hasło: admin123")
    print("\nZmień hasło po pierwszym logowaniu!")
    print("=" * 50 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
