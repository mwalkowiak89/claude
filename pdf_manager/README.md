# PDF Manager

System zarządzania dostępem do plików PDF z automatycznymi powiadomieniami email.

## Funkcjonalności

- System logowania (użytkownicy + administratorzy)
- Użytkownicy widzą tylko pliki do których mają dostęp
- Administrator może:
  - Uploadować pliki PDF
  - Zarządzać użytkownikami
  - Przypisywać dostęp do plików
- Automatyczne powiadomienia email przy aktualizacji plików
- Responsive UI z Bootstrap 5

## Instalacja

1. Sklonuj repozytorium i przejdź do katalogu projektu:
```bash
cd pdf_manager
```

2. Utwórz i aktywuj wirtualne środowisko:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# lub
venv\Scripts\activate  # Windows
```

3. Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

4. Skopiuj plik konfiguracyjny i dostosuj ustawienia:
```bash
cp .env.example .env
# Edytuj .env i ustaw odpowiednie wartości
```

5. Uruchom aplikację:
```bash
python run.py
```

6. Otwórz przeglądarkę: http://localhost:5000

## Domyślne konto administratora

- **Email:** admin@example.com
- **Hasło:** admin123

**Zmień hasło po pierwszym logowaniu!**

## Konfiguracja Email

Aby włączyć powiadomienia email, ustaw w pliku `.env`:

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=twoj-email@gmail.com
MAIL_PASSWORD=haslo-aplikacji
MAIL_DEFAULT_SENDER=noreply@twojaaplikacja.pl
```

Dla Gmail zaleca się użycie "hasła aplikacji" zamiast głównego hasła.

## Struktura projektu

```
pdf_manager/
├── app/
│   ├── __init__.py          # Fabryka aplikacji
│   ├── models.py             # Modele bazy danych
│   ├── forms.py              # Formularze WTForms
│   ├── email.py              # Obsługa emaili
│   ├── routes/
│   │   ├── auth.py           # Logowanie/wylogowanie
│   │   ├── main.py           # Główne widoki użytkownika
│   │   └── admin.py          # Panel administracyjny
│   ├── templates/            # Szablony HTML
│   └── static/               # CSS, JS, obrazy
├── uploads/                  # Przesłane pliki PDF
├── config.py                 # Konfiguracja
├── requirements.txt          # Zależności
└── run.py                    # Punkt wejścia
```

## Technologie

- Flask 3.0
- Flask-Login (autentykacja)
- Flask-SQLAlchemy (ORM)
- Flask-Mail (powiadomienia email)
- Flask-WTF (formularze)
- Bootstrap 5 (UI)
- SQLite (baza danych)

## Licencja

MIT
