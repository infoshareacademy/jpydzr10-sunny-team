# Deployment — SunnyTeamProject

## Wymagania wstępne

Przed rozpoczęciem upewnij się że masz zainstalowane:
- Python 3.12+
- MySQL
- Virtualenv (`.venv` w folderze projektu)
- Systemowe zależności do kompilacji `mysqlclient`:

```bash
sudo apt install pkg-config python3-dev default-libmysqlclient-dev build-essential
```

---

## Gunicorn

### Instalacja

1. Zainstaluj Gunicorn w virtualenvie projektu:

```bash
pip install gunicorn
```

2. Skopiuj plik `deploy/gunicorn.service` do folderu systemd:

```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/gunicorn.service
```

3. Otwórz plik i podmień placeholdery na właściwe wartości:
   - `Username` → nazwa twojego użytkownika systemowego
   - `path_to_project` → ścieżka do folderu projektu

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

4. Aktywuj i uruchom serwis:

```bash
sudo systemctl daemon-reload        # przeładuj konfigurację systemd
sudo systemctl enable gunicorn      # uruchamiaj automatycznie przy starcie systemu
sudo systemctl start gunicorn       # uruchom teraz
sudo systemctl status gunicorn      # sprawdź czy działa
```

Po poprawnej instalacji aplikacja powinna być dostępna lokalnie pod adresem `http://127.0.0.1:8000`.

---

## Nginx

### Instalacja

1. Zainstaluj Nginx:

```bash
sudo apt install nginx
```

2. Skopiuj plik konfiguracyjny do folderu Nginx:

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/sunny-team
```

3. Otwórz plik i podmień `path_to_project` na właściwą ścieżkę do folderu projektu:

```bash
sudo nano /etc/nginx/sites-available/sunny-team
```

4. Wygeneruj pliki statyczne Django:

```bash
python manage.py collectstatic
```

5. Aktywuj konfigurację i uruchom Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/sunny-team /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # usuń domyślną konfigurację Nginx
sudo nginx -t                             # sprawdź poprawność konfiguracji
sudo systemctl start nginx
sudo systemctl enable nginx               # uruchamiaj automatycznie przy starcie
```

Po poprawnej instalacji aplikacja powinna być dostępna pod adresem `http://localhost`.
