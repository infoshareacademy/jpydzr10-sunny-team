from datetime import datetime

from auth.login import login
from startup.admin_check import admin_exist
from models.admin import Admin
from models.worker import Worker
from models.manager import Manager
from models.hr import HR
from database.database import load_users, create_user
from leave_requests.leave_request import LeaveRequest
from leave_requests.display_vacations import display_vacations
from database.leave_requests_db import load_leave_requests, save_leave_requests
from permission_system.permission import Permission


# ──────────────────────────────────────────────
#  HELPERY
# ──────────────────────────────────────────────

def _pick_request(leave_requests: list):
    """Wypisuje dostępne wnioski i zwraca wybrany przez admina obiekt (lub None)."""
    if not leave_requests:
        print("Brak wniosków urlopowych.")
        return None

    print("\nDostępne wnioski:")
    for i, req in enumerate(leave_requests):
        print(f"  [{i}] {req.first_name} {req.last_name} | "
              f"{req.start_date} – {req.end_date} | "
              f"Status: {req.status.value}")

    try:
        idx = int(input("Podaj numer wniosku: "))
        return leave_requests[idx]
    except (ValueError, IndexError):
        print("Nieprawidłowy numer wniosku.")
        return None


def _pick_user(users: dict):
    """Wypisuje dostępnych użytkowników i zwraca wybranego (lub None)."""
    if not users:
        print("Brak użytkowników w bazie.")
        return None

    print("\nUżytkownicy w systemie:")
    for uid, u in users.items():
        print(f"  [{uid}] {u.username} | rola: {u.role}")

    try:
        uid = int(input("Podaj ID użytkownika: "))
        return users.get(uid)
    except ValueError:
        print("Nieprawidłowe ID.")
        return None


# ──────────────────────────────────────────────
#  PANEL ADMINA
# ──────────────────────────────────────────────

def admin_menu(admin, leave_requests: list):
    while True:
        print(f"\n=== Panel Admina ({admin.username}) ===")
        print("--- Wnioski urlopowe ---")
        print("1. Zatwierdź wniosek")
        print("2. Odrzuć wniosek")
        print("3. Anuluj wniosek")
        print("4. Zmień daty wniosku")
        print("5. Wyświetl wnioski (lista)")
        print("--- Użytkownicy ---")
        print("6. Lista użytkowników")
        print("7. Dodaj użytkownika")
        print("8. Wyświetl urlopy użytkownika")
        print("9. Resetuj hasło użytkownika")
        print("---")
        print("0. Wyloguj")

        choice = input("\nWybierz opcję: ").strip()

        # ── Zatwierdzenie wniosku ──────────────────
        if choice == "1":
            req = _pick_request(leave_requests)
            if req:
                try:
                    req.approve(admin.username)
                    print("✓ Wniosek zatwierdzony.")
                except Exception as e:
                    print(f"Błąd: {e}")

        # ── Odrzucenie wniosku ─────────────────────
        elif choice == "2":
            req = _pick_request(leave_requests)
            if req:
                try:
                    req.rejected(admin.username)
                    print("✓ Wniosek odrzucony.")
                except Exception as e:
                    print(f"Błąd: {e}")

        # ── Anulowanie wniosku ─────────────────────
        elif choice == "3":
            req = _pick_request(leave_requests)
            if req:
                try:
                    req.cancel_request(admin.username, datetime.now())
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        # ── Zmiana dat wniosku ─────────────────────
        elif choice == "4":
            req = _pick_request(leave_requests)
            if req:
                try:
                    new_start = datetime.strptime(
                        input("Nowa data startu (YYYY-MM-DD): "), "%Y-%m-%d"
                    ).date()
                    new_end = datetime.strptime(
                        input("Nowa data końca  (YYYY-MM-DD): "), "%Y-%m-%d"
                    ).date()
                    days = int(input("Liczba dni urlopu: "))
                    req.change_request(new_start, new_end, days)
                    print("✓ Wniosek zmieniony.")
                except ValueError as e:
                    print(f"Błąd danych: {e}")
                except Exception as e:
                    print(f"Błąd: {e}")

        # ── Lista wniosków ─────────────────────────
        elif choice == "5":
            if not leave_requests:
                print("Brak wniosków urlopowych.")
            else:
                print("\n=== Wszystkie wnioski ===")
                for i, req in enumerate(leave_requests):
                    print(f"[{i}] {req.first_name} {req.last_name} | "
                          f"{req.start_date} – {req.end_date} | "
                          f"Status: {req.status.value} | "
                          f"Zatwierdził: {req.who_confirmed or '—'}")

        # ── Lista użytkowników ─────────────────────
        elif choice == "6":
            users = load_users()
            if not users:
                print("Brak użytkowników w bazie.")
            else:
                print("\n=== Użytkownicy ===")
                for uid, u in users.items():
                    print(f"  ID: {uid} | {u.username} | rola: {u.role}")

        # ── Dodanie użytkownika ────────────────────
        elif choice == "7":
            try:
                users = load_users()
                new_id = max(users.keys(), default=0) + 1
                username = input("Nazwa użytkownika: ").strip()
                password = input("Hasło (min. 6 znaków): ").strip()
                print("Role: Admin / Manager / HR / Employee")
                role = input("Rola: ").strip()
                user = create_user(new_id, username, password, role)
                print(f"✓ Użytkownik '{user.username}' (ID {user.user_id}) dodany.")
            except Exception as e:
                print(f"Błąd: {e}")

        # ── Urlopy użytkownika ─────────────────────
        elif choice == "8":
            users = load_users()
            user = _pick_user(users)
            if user:
                display_vacations(user.user_id)
        # ── Reset hasła ────────────────────────────
        elif choice == "9":
            from auth.login import hash_password
            from database.database import user_database, save_users
            users = load_users()
            user = _pick_user(users)
            if user:
                new_password = input("Nowe hasło (min. 6 znaków): ").strip()
                if len(new_password) < 6:
                    print("Hasło za krótkie.")
                else:
                    user_database[user.user_id].password_hash = hash_password(new_password)
                    save_users()
                    print(f"✓ Hasło użytkownika '{user.username}' zostało zresetowane.")

        # ── Wylogowanie ────────────────────────────
        elif choice == "0":
            print("Wylogowano.")
            break

        else:
            print("Nieznana opcja, spróbuj ponownie.")


# ──────────────────────────────────────────────
#  PANEL WORKERA (pracownik)
# ──────────────────────────────────────────────

def worker_menu(user, leave_requests: list):
    while True:
        print(f"\n=== Panel Pracownika ({user.username}) ===")
        if hasattr(user, "get_leave_days"):
            print(f"Dostępne dni urlopu: {user.get_leave_days()} / {user.total_leave_days}")
        print("1. Złóż wniosek urlopowy")
        print("2. Moje urlopy")
        print("3. Anuluj wniosek")
        print("0. Wyloguj")

        choice = input("\nWybierz opcję: ").strip()

        if choice == "1":
            try:
                start = datetime.strptime(
                    input("Data startu (YYYY-MM-DD): "), "%Y-%m-%d"
                ).date()
                end = datetime.strptime(
                    input("Data końca  (YYYY-MM-DD): "), "%Y-%m-%d"
                ).date()
                days = int(input("Liczba dni urlopu: "))
                req = LeaveRequest(
                    user.user_id,
                    getattr(user, "first_name", user.username),
                    getattr(user, "last_name", ""),
                    start, end, days
                )
                leave_requests.append(req)
                print(f"✓ Wniosek złożony. Status: {req.status.value}")
            except ValueError as e:
                print(f"Błąd danych: {e}")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "2":
            display_vacations(user.user_id)

        elif choice == "3":
            my_requests = [r for r in leave_requests if r.employee_id == user.user_id]
            req = _pick_request(my_requests)
            if req:
                try:
                    req.cancel_request(user.username, datetime.now())
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "0":
            print("Wylogowano.")
            break
        else:
            print("Nieznana opcja, spróbuj ponownie.")


# ──────────────────────────────────────────────
#  PANEL MANAGERA
# ──────────────────────────────────────────────

def manager_menu(user: Manager, leave_requests: list):
    while True:
        print(f"\n=== Panel Managera ({user.username}) ===")
        if hasattr(user, "get_leave_days"):
            print(f"Dostępne dni urlopu: {user.get_leave_days()} / {user.total_leave_days}")
        print("--- Moje wnioski ---")
        print("1. Złóż wniosek urlopowy")
        print("2. Moje urlopy")
        print("3. Anuluj swój wniosek")
        print("--- Zespół ---")
        print("4. Lista wniosków zespołu")
        print("5. Zatwierdź wniosek")
        print("6. Odrzuć wniosek")
        print("0. Wyloguj")

        choice = input("\nWybierz opcję: ").strip()

        if choice == "1":
            try:
                start = datetime.strptime(
                    input("Data startu (YYYY-MM-DD): "), "%Y-%m-%d"
                ).date()
                end = datetime.strptime(
                    input("Data końca  (YYYY-MM-DD): "), "%Y-%m-%d"
                ).date()
                days = int(input("Liczba dni urlopu: "))
                req = LeaveRequest(
                    user.user_id,
                    getattr(user, "first_name", user.username),
                    getattr(user, "last_name", ""),
                    start, end, days
                )
                leave_requests.append(req)
                print(f"✓ Wniosek złożony. Status: {req.status.value}")
            except ValueError as e:
                print(f"Błąd danych: {e}")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "2":
            display_vacations(user.user_id)

        elif choice == "3":
            my_requests = [r for r in leave_requests if r.employee_id == user.user_id]
            req = _pick_request(my_requests)
            if req:
                try:
                    req.cancel_request(user.username, datetime.now())
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "4":
            team_requests = [r for r in leave_requests if r.employee_id != user.user_id]
            if not team_requests:
                print("Brak wniosków od innych pracowników.")
            else:
                print("\n=== Wnioski zespołu ===")
                for i, req in enumerate(team_requests):
                    print(f"[{i}] {req.first_name} {req.last_name} | "
                          f"{req.start_date} – {req.end_date} | "
                          f"Status: {req.status.value}")

        elif choice == "5":
            team_requests = [r for r in leave_requests if r.employee_id != user.user_id]
            req = _pick_request(team_requests)
            if req:
                try:
                    req.approve(user.username)
                    print("✓ Wniosek zatwierdzony.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "6":
            team_requests = [r for r in leave_requests if r.employee_id != user.user_id]
            req = _pick_request(team_requests)
            if req:
                try:
                    req.rejected(user.username)
                    print("✓ Wniosek odrzucony.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "0":
            print("Wylogowano.")
            break
        else:
            print("Nieznana opcja, spróbuj ponownie.")


# ──────────────────────────────────────────────
#  PANEL HR
# ──────────────────────────────────────────────

def hr_menu(user: HR, leave_requests: list):
    while True:
        print(f"\n=== Panel HR ({user.username}) ===")
        if hasattr(user, "get_leave_days"):
            print(f"Dostępne dni urlopu: {user.get_leave_days()} / {user.total_leave_days}")
        print("--- Moje wnioski ---")
        print("1. Złóż wniosek urlopowy")
        print("2. Moje urlopy")
        print("3. Anuluj swój wniosek")
        print("--- Użytkownicy ---")
        print("4. Lista użytkowników")
        print("5. Dodaj użytkownika")
        print("6. Urlopy użytkownika")
        print("0. Wyloguj")

        choice = input("\nWybierz opcję: ").strip()

        if choice == "1":
            try:
                start = datetime.strptime(
                    input("Data startu (YYYY-MM-DD): "), "%Y-%m-%d"
                ).date()
                end = datetime.strptime(
                    input("Data końca  (YYYY-MM-DD): "), "%Y-%m-%d"
                ).date()
                days = int(input("Liczba dni urlopu: "))
                req = LeaveRequest(
                    user.user_id,
                    getattr(user, "first_name", user.username),
                    getattr(user, "last_name", ""),
                    start, end, days
                )
                leave_requests.append(req)
                print(f"✓ Wniosek złożony. Status: {req.status.value}")
            except ValueError as e:
                print(f"Błąd danych: {e}")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "2":
            display_vacations(user.user_id)

        elif choice == "3":
            my_requests = [r for r in leave_requests if r.employee_id == user.user_id]
            req = _pick_request(my_requests)
            if req:
                try:
                    req.cancel_request(user.username, datetime.now())
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "4":
            users = load_users()
            if not users:
                print("Brak użytkowników w bazie.")
            else:
                print("\n=== Użytkownicy ===")
                for uid, u in users.items():
                    print(f"  ID: {uid} | {u.username} | rola: {u.role}")

        elif choice == "5":
            try:
                users = load_users()
                new_id = max(users.keys(), default=0) + 1
                username = input("Nazwa użytkownika: ").strip()
                password = input("Hasło (min. 6 znaków): ").strip()
                print("Role: Admin / Manager / HR / Employee")
                role = input("Rola: ").strip()
                new_user = create_user(new_id, username, password, role)
                print(f"✓ Użytkownik '{new_user.username}' (ID {new_user.user_id}) dodany.")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "6":
            users = load_users()
            picked = _pick_user(users)
            if picked:
                display_vacations(picked.user_id)

        elif choice == "0":
            print("Wylogowano.")
            break
        else:
            print("Nieznana opcja, spróbuj ponownie.")


# ──────────────────────────────────────────────
#  START APLIKACJI
# ──────────────────────────────────────────────

def start_app():
    admin_exist()
    leave_requests = []

    while True:
        print("\n*** Logowanie ***")
        username = input("Nazwa użytkownika: ").strip()
        password = input("Hasło: ").strip()

        user = login(username, password)

        if user is None:
            print("Niepoprawne dane logowania.")
            continue

        if isinstance(user, Admin):
            admin_menu(user, leave_requests)
        elif isinstance(user, Manager):
            manager_menu(user, leave_requests)
        elif isinstance(user, HR):
            hr_menu(user, leave_requests)
        elif isinstance(user, Worker) or user.role == "Employee":
            worker_menu(user, leave_requests)
        else:
            print("Nieznana rola — brak panelu.")


if __name__ == "__main__":
    start_app()