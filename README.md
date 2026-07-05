# jpydzr10-sunny-team — Kalendarz urlopowy

Aplikacja webowa (Django) do zarządzania wnioskami urlopowymi w firmie: składanie,
zatwierdzanie/odrzucanie wniosków, kalendarz zespołu, raporty wykorzystania urlopów
oraz zarządzanie użytkownikami — z podziałem na role (Admin, Manager, HR, Worker).

Pełna dokumentacja wdrożenia produkcyjnego (Gunicorn + Nginx + systemd) znajduje się
w [`deploy/DEPLOY_README.md`](deploy/DEPLOY_README.md), a konfiguracja MySQL pod produkcję
w [`docs/mysql_setup.md`](docs/mysql_setup.md). Ten README opisuje uruchomienie **lokalne/deweloperskie**.

## Stos technologiczny

- Python 3.12+
- Django 5.2
- MySQL 8.0
- Gunicorn + Nginx (opcjonalnie, do trybu zbliżonego do produkcyjnego)

## 1. Wymagania wstępne

Na Ubuntu zainstaluj zależności systemowe potrzebne do skompilowania sterownika MySQL:

```bash
sudo apt update
sudo apt install python3-venv python3-dev default-libmysqlclient-dev pkg-config build-essential
sudo apt install mysql-server
```

Upewnij się, że MySQL działa:

```bash
sudo systemctl status mysql
```

## 2. Klonowanie repozytorium i środowisko wirtualne

```bash
git clone https://github.com/infoshareacademy/jpydzr10-sunny-team.git
cd jpydzr10-sunny-team

python3 -m venv .venv
source .venv/bin/activate
```

## 3. Instalacja zależności

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Uwaga:** projekt korzysta z bazy MySQL, więc potrzebny jest też pakiet `mysqlclient`
> (dodany do `requirements.txt`). Jeśli instalacja się nie powiedzie, sprawdź czy zostały
> zainstalowane zależności systemowe z kroku 1.

## 4. Konfiguracja bazy danych

Utwórz lokalną bazę danych MySQL o nazwie `calendar_db`:

```bash
mysql -u root -p -e "CREATE DATABASE calendar_db CHARACTER SET utf8mb4;"
```

Dane logowania do bazy są zdefiniowane w `calendar_app/settings.py` (sekcja `DATABASES`).
Jeśli Twoja lokalna instalacja MySQL ma inne dane dostępowe, podmień je w tym pliku
(`USER`, `PASSWORD`, `HOST`, `PORT`) przed przejściem dalej.

## 5. Migracje

```bash
python manage.py migrate
```

## 6. Dane startowe (opcjonalnie, ale zalecane)

Projekt zawiera gotowy fixture `startup/seed.json` (użytkownicy, profile, wnioski w jednej komendzie):

```bash
python manage.py loaddata startup/seed.json
```

## 7. Konto administratora

Aby mieć od razu dostęp do panelu Django (`/admin/`) oraz roli Admin w aplikacji:

```bash
python manage.py createsuperuser
```

Po utworzeniu konta ustaw mu rolę `Admin` (np. przez `/admin/` albo powłokę Django):

```bash
python manage.py shell -c "from accounts.models import User; u = User.objects.get(username='TWOJA_NAZWA'); u.role='Admin'; u.save()"
```

## 8. Pliki statyczne (opcjonalnie przy lokalnym uruchomieniu przez `runserver`)

Do zwykłego developmentu `runserver` obsługuje statyki automatycznie — ten krok jest
potrzebny tylko jeśli chcesz uruchomić projekt przez Gunicorn/Nginx lokalnie:

```bash
python manage.py collectstatic
```

## 9. Uruchomienie serwera deweloperskiego

```bash
python manage.py runserver
```

Aplikacja będzie dostępna pod adresem: **http://127.0.0.1:8000/**

Logowanie: `http://127.0.0.1:8000/login/`
Panel administracyjny Django: `http://127.0.0.1:8000/admin/`

## 10. Testy

```bash
python manage.py test
```

## 11. Uruchomienie w trybie zbliżonym do produkcyjnego (Gunicorn + Nginx, lokalnie)

Jeśli chcesz przetestować lokalnie konfigurację zbliżoną do produkcyjnej (Gunicorn +
Nginx zamiast `runserver`), postępuj zgodnie z instrukcją w
[`deploy/DEPLOY_README.md`](deploy/DEPLOY_README.md). W skrócie:

```bash
pip install gunicorn
python manage.py collectstatic
gunicorn --bind 127.0.0.1:8000 calendar_app.wsgi:application
```

> **Częsty problem:** Gunicorn nie przeładowuje kodu automatycznie po zmianach — po
> edycji plików trzeba go zrestartować (`Ctrl+C` i uruchomić ponownie, albo
> `sudo systemctl restart gunicorn` przy konfiguracji z systemd).
>
> Jeśli statyki się nie ładują lub routing nie działa, sprawdź czy w
> `deploy/gunicorn.service` i `deploy/nginx.conf` ścieżki `path_to_project`/`Username`
> zostały podmienione na rzeczywiste wartości Twojego środowiska.

## Struktura projektu (skrót)

```
calendar_app/    # ustawienia i routing główny Django
accounts/        # model User, role, uprawnienia, zarządzanie użytkownikami
leaves/          # wnioski urlopowe, kalendarz zespołu, dashboard
reports/         # raporty wykorzystania urlopów, eksport CSV
logs/            # historia zmian/akcji w systemie
admin_panel/     # panel administracyjny aplikacji (niezależny od /admin/ Django)
login/           # logowanie/wylogowanie
startup/         # przykładowe dane startowe (CSV, fixture seed.json)
deploy/          # konfiguracja Gunicorn + Nginx
docs/            # dodatkowa dokumentacja (m.in. role i uprawnienia, MySQL produkcyjny)
```

## Role i uprawnienia

Pełna tabela ról i uprawnień znajduje się w [`docs/PERMISSIONS.md`](docs/PERMISSIONS.md).
