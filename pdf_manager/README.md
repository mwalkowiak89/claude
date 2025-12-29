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
- Automatyczne backupy bazy i plików z panel administracyjnym
- Wielojęzyczny interfejs użytkownika (PL, EN, DE, PT, FR, ES)

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

## Kopie zapasowe (Backup)

System backupów umożliwia tworzenie kopii zapasowych bazy danych i plików PDF.

### Ręczne tworzenie backupu:
```bash
python backup.py
```

### Zarządzanie backupami z CLI:
```bash
# Utworzenie backupu
python backup.py --create

# Lista backupów
python backup.py --list

# Usunięcie starych backupów (domyślnie >7 dni)
python backup.py --cleanup

# Przywrócenie backupu
python backup.py --restore nazwa_backupu.zip
```

### Automatyczne backupy (cron):
```bash
# Edytuj crontab
crontab -e

# Dodaj linię (backup codziennie o 2:00):
0 2 * * * cd /ścieżka/do/projektu && /ścieżka/do/venv/bin/python backup.py >> backups/backup.log 2>&1
```

### Panel administracyjny:
Backupy można także zarządzać z poziomu panelu administracyjnego pod adresem `/admin/backups`:
- Tworzenie nowych backupów
- Pobieranie istniejących backupów
- Przywracanie z backupu (wymaga potwierdzenia hasłem)
- Usuwanie niepotrzebnych backupów

**Uwaga:** Backupy są automatycznie przechowywane przez 7 dni.

## Wielojęzyczny interfejs (i18n)

Aplikacja obsługuje 6 języków: Polski, English, Deutsch, Português, Français, Español.

### Przełączanie języka:
- Dropdown z flagami w pasku nawigacyjnym
- Język zapisywany w sesji (zalogowani) i cookie (niezalogowani)
- Automatyczne wykrywanie języka przeglądarki

### Zarządzanie tłumaczeniami:

```bash
# Wyciągnij teksty do przetłumaczenia
pybabel extract -F babel.cfg -o messages.pot .

# Inicjalizuj nowy język (np. włoski)
pybabel init -i messages.pot -d app/translations -l it

# Zaktualizuj istniejące tłumaczenia
pybabel update -i messages.pot -d app/translations

# Skompiluj tłumaczenia (wymagane po każdej zmianie .po)
pybabel compile -d app/translations
```

### Struktura plików tłumaczeń:
```
app/translations/
├── pl/LC_MESSAGES/messages.po
├── en/LC_MESSAGES/messages.po
├── de/LC_MESSAGES/messages.po
├── pt/LC_MESSAGES/messages.po
├── fr/LC_MESSAGES/messages.po
└── es/LC_MESSAGES/messages.po
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
│   ├── translations/         # Pliki tłumaczeń (i18n)
│   └── static/               # Pliki statyczne (CSS)
├── migrations/               # Migracje bazy danych
├── uploads/                  # Przesłane pliki PDF
├── backups/                  # Kopie zapasowe
│   └── daily/                # Codzienne backupy
├── babel.cfg                 # Konfiguracja Babel
├── backup.py                 # Skrypt backupu
├── config.py                 # Konfiguracja
├── run.py                    # Punkt wejścia
└── requirements.txt          # Zależności Python
```

## Licencja

MIT
