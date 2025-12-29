# PDF Manager

Aplikacja Flask do zarządzania dostępem do plików PDF z uwierzytelnianiem użytkowników.

## Funkcje

- Uwierzytelnianie użytkowników (użytkownicy + administratorzy)
- Dwuskładnikowe logowanie (2FA) dla administratorów
- Zarządzanie plikami PDF z wersjonowaniem
- Kontrola dostępu do plików
- Powiadomienia email o nowych plikach i aktualizacjach
- Wielojęzyczne szablony email (PL, EN, DE, PT, FR, ES)
- Rate limiting (ochrona przed brute-force)
- Tryb ciemny (Dark Mode)

## Instalacja

```bash
# Klonowanie repozytorium
git clone <repository-url>
cd pdf_manager

# Utworzenie wirtualnego środowiska
python -m venv venv
source venv/bin/activate  # Linux/Mac
# lub: venv\Scripts\activate  # Windows

# Instalacja zależności
pip install -r requirements.txt

# Konfiguracja zmiennych środowiskowych
cp .env.example .env
# Edytuj .env i ustaw wartości

# Inicjalizacja bazy danych
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Uruchomienie aplikacji
flask run
```

## Migracje bazy danych

Projekt używa Flask-Migrate do zarządzania schematem bazy danych.

### Pierwsza konfiguracja:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### Po zmianach w models.py:
```bash
flask db migrate -m "Opis zmian"
flask db upgrade
```

### Cofnięcie ostatniej migracji:
```bash
flask db downgrade
```

### Podgląd historii migracji:
```bash
flask db history
```

### Podgląd aktualnej wersji:
```bash
flask db current
```

## Konfiguracja

Utwórz plik `.env` w głównym katalogu projektu:

```env
SECRET_KEY=twoj-tajny-klucz
DATABASE_URL=sqlite:///app.db

# Email (opcjonalnie)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=twoj@email.com
MAIL_PASSWORD=haslo-aplikacji

# Rate limiting (opcjonalnie)
RATELIMIT_WHITELIST=127.0.0.1
```

## Domyślne konto administratora

Po pierwszym uruchomieniu tworzone jest konto:
- Email: `admin@example.com`
- Hasło: `admin123`

**Ważne:** Zmień hasło po pierwszym logowaniu!

## Struktura projektu

```
pdf_manager/
├── app/
│   ├── __init__.py          # Fabryka aplikacji
│   ├── models.py             # Modele bazy danych
│   ├── forms.py              # Formularze WTForms
│   ├── email.py              # Funkcje wysyłki email
│   ├── routes/
│   │   ├── auth.py           # Logowanie, 2FA
│   │   ├── main.py           # Widoki użytkownika
│   │   └── admin.py          # Panel administracyjny
│   ├── templates/            # Szablony Jinja2
│   └── static/               # Pliki statyczne (CSS)
├── migrations/               # Migracje bazy danych
├── uploads/                  # Przesłane pliki PDF
├── config.py                 # Konfiguracja
├── run.py                    # Punkt wejścia
└── requirements.txt          # Zależności Python
```

## Licencja

MIT
