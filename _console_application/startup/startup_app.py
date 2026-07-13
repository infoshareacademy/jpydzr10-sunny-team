from datetime import datetime

from _console_application.auth.login import login
from _console_application.startup.admin_check import admin_exist
from _console_application.models.admin import Admin
from _console_application.models.worker import Worker
from _console_application.models.manager import Manager
from _console_application.models.hr import HR
from _console_application.database.database import load_users, create_user, user_database, save_users
from _console_application.database.leave_requests_db import load_leave_requests, save_leave_requests
from _console_application.leave_requests.leave_request import LeaveRequest
from _console_application.leave_requests.display_vacations import display_vacations
from _console_application.logs.log_history import app_log
from _console_application.perrmission_system.permission  import Permission


# ──────────────────────────────────────────────
#  HELPERY
# ──────────────────────────────────────────────

def _check(role: str, action: str) -> bool:
    """Sprawdza uprawnienie i drukuje komunikat jeśli brak dostępu."""
    if not Permission.verifyPermission(role, action):
        print(f"Brak uprawnień: rola '{role}' nie może wykonać akcji '{action}'.")
        return False
    return True


def _pick_request(leave_requests: dict):
    """Wypisuje dostępne wnioski i zwraca (req_id, req) lub (None, None)."""
    if not leave_requests:
        print("Brak wniosków urlopowych.")
        return None, None

    print("\nDostępne wnioski:")
    for req_id, req in leave_requests.items():
        print(f"  [{req_id}] {req.first_name} {req.last_name} | "
              f"{req.start_date} – {req.end_date} | "
              f"Status: {req.status.value}")

    try:
        req_id = int(input("Podaj ID wniosku: "))
        if req_id not in leave_requests:
            print("Nie znaleziono wniosku o podanym ID.")
            return None, None
        return req_id, leave_requests[req_id]
    except ValueError:
        print("Nieprawidłowe ID.")
        return None, None


def _pick_user(users: dict):
    """Wypisuje dostępnych użytkowników i zwraca wybranego (lub None)."""
    if not users:
        print("Brak użytkowników w bazie.")
        return None

    print("\nUżytkownicy w systemie:")
    for uid, u in users.items():
        status = "aktywny" if u.is_active else "nieaktywny"
        print(f"  [{uid}] {u.username} | rola: {u.role} | {status}")

    try:
        uid = int(input("Podaj ID użytkownika: "))
        return users.get(uid)
    except ValueError:
        print("Nieprawidłowe ID.")
        return None


# ──────────────────────────────────────────────
#  PANEL ADMINA
# ──────────────────────────────────────────────

def admin_menu(admin):
    role = admin.role
    while True:
        leave_requests = load_leave_requests()

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

        if choice == "1":
            if not _check(role, "can_approve_request"):
                continue
            req_id, req = _pick_request(leave_requests)
            if req:
                try:
                    req.approve(admin.username)
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(admin.user_id, "zatwierdz", "leave_request")
                    print("✓ Wniosek zatwierdzony.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "2":
            if not _check(role, "can_reject_request"):
                continue
            req_id, req = _pick_request(leave_requests)
            if req:
                try:
                    req.rejected(admin.username)
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(admin.user_id, "odrzuc", "leave_request")
                    print("✓ Wniosek odrzucony.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "3":
            if not _check(role, "can_cancel_request"):
                continue
            req_id, req = _pick_request(leave_requests)
            if req:
                try:
                    req.cancel_request(admin.username, datetime.now())
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(admin.user_id, "anuluj", "leave_request")
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "4":
            if not _check(role, "can_change_request"):
                continue
            req_id, req = _pick_request(leave_requests)
            if req:
                try:
                    new_start = datetime.strptime(input("Nowa data startu (YYYY-MM-DD): "), "%Y-%m-%d").date()
                    new_end = datetime.strptime(input("Nowa data końca  (YYYY-MM-DD): "), "%Y-%m-%d").date()
                    days = int(input("Liczba dni urlopu: "))
                    req.change_request(new_start, new_end, days)
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(admin.user_id, "edytuj", "leave_request")
                    print("✓ Wniosek zmieniony.")
                except ValueError as e:
                    print(f"Błąd danych: {e}")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "5":
            if not _check(role, "can_see_all_requests"):
                continue
            if not leave_requests:
                print("Brak wniosków urlopowych.")
            else:
                print("\n=== Wszystkie wnioski ===")
                for req_id, req in leave_requests.items():
                    print(f"  [{req_id}] {req.first_name} {req.last_name} | "
                          f"{req.start_date} – {req.end_date} | "
                          f"Status: {req.status.value} | "
                          f"Zatwierdził: {req.who_confirmed or '—'}")

        elif choice == "6":
            if not _check(role, "can_list_users"):
                continue
            users = load_users()
            if not users:
                print("Brak użytkowników w bazie.")
            else:
                print("\n=== Użytkownicy ===")
                for uid, u in users.items():
                    status = "aktywny" if u.is_active else "nieaktywny"
                    print(f"  ID: {uid} | {u.username} | rola: {u.role} | {status}")

        elif choice == "7":
            if not _check(role, "can_add_user"):
                continue
            try:
                users = load_users()
                new_id = max(users.keys(), default=0) + 1
                username = input("Nazwa użytkownika: ").strip()
                password = input("Hasło (min. 6 znaków): ").strip()
                print("Role: Admin / Manager / HR / Worker")
                role_new = input("Rola: ").strip()
                user = create_user(new_id, username, password, role_new)
                app_log.add_new_change(admin.user_id, "dodaj", f"user:{role_new}")
                print(f"✓ Użytkownik '{user.username}' (ID {user.user_id}) dodany.")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "8":
            if not _check(role, "can_see_user_vacations"):
                continue
            users = load_users()
            user = _pick_user(users)
            if user:
                display_vacations(user.user_id)

        elif choice == "9":
            if not _check(role, "can_reset_password"):
                continue
            from _console_application.auth.login import hash_password
            users = load_users()
            user = _pick_user(users)
            if user:
                new_password = input("Nowe hasło (min. 6 znaków): ").strip()
                if len(new_password) < 6:
                    print("Hasło za krótkie.")
                else:
                    user_database[user.user_id].password_hash = hash_password(new_password)
                    save_users()
                    app_log.add_new_change(admin.user_id, "reset_hasla", f"user:{user.user_id}")
                    print(f"✓ Hasło użytkownika '{user.username}' zostało zresetowane.")

        elif choice == "0":
            print("Wylogowano.")
            break

        else:
            print("Nieznana opcja, spróbuj ponownie.")


# ──────────────────────────────────────────────
#  PANEL WORKERA
# ──────────────────────────────────────────────

def worker_menu(user):
    role = user.role
    while True:
        leave_requests = load_leave_requests()

        print(f"\n=== Panel Pracownika ({user.username}) ===")
        if hasattr(user, "get_leave_days"):
            print(f"Dostępne dni urlopu: {user.get_leave_days()} / {user.total_leave_days}")
        print("1. Złóż wniosek urlopowy")
        print("2. Moje urlopy")
        print("3. Anuluj wniosek")
        print("4. Zmień daty wniosku")
        print("0. Wyloguj")

        choice = input("\nWybierz opcję: ").strip()

        if choice == "1":
            if not _check(role, "can_submit_request"):
                continue
            try:
                start = datetime.strptime(input("Data startu (YYYY-MM-DD): "), "%Y-%m-%d").date()
                end = datetime.strptime(input("Data końca  (YYYY-MM-DD): "), "%Y-%m-%d").date()
                days = int(input("Liczba dni urlopu: "))
                req = LeaveRequest(
                    user.user_id,
                    getattr(user, "first_name", user.username),
                    getattr(user, "last_name", ""),
                    start, end, days
                )
                new_id = max(leave_requests.keys(), default=0) + 1
                leave_requests[new_id] = req
                save_leave_requests(leave_requests)
                app_log.add_new_change(user.user_id, "dodaj", "leave_request")
                print(f"✓ Wniosek złożony. Status: {req.status.value}")
            except ValueError as e:
                print(f"Błąd danych: {e}")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "2":
            if not _check(role, "can_see_own_requests"):
                continue
            display_vacations(user.user_id)

        elif choice == "3":
            if not _check(role, "can_cancel_request"):
                continue
            # Worker może anulować tylko swoje wnioski
            my_requests = {rid: r for rid, r in leave_requests.items() if r.employee_id == user.user_id}
            req_id, req = _pick_request(my_requests)
            if req:
                try:
                    req.cancel_request(user.username, datetime.now())
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(user.user_id, "anuluj", "leave_request")
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "4":
            if not _check(role, "can_change_request"):
                continue
            # Worker może zmieniać tylko swoje wnioski
            my_requests = {rid: r for rid, r in leave_requests.items() if r.employee_id == user.user_id}
            req_id, req = _pick_request(my_requests)
            if req:
                try:
                    new_start = datetime.strptime(input("Nowa data startu (YYYY-MM-DD): "), "%Y-%m-%d").date()
                    new_end = datetime.strptime(input("Nowa data końca  (YYYY-MM-DD): "), "%Y-%m-%d").date()
                    days = int(input("Liczba dni urlopu: "))
                    req.change_request(new_start, new_end, days)
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(user.user_id, "edytuj", "leave_request")
                    print("✓ Wniosek zmieniony.")
                except ValueError as e:
                    print(f"Błąd danych: {e}")
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

def manager_menu(user):
    role = user.role
    while True:
        leave_requests = load_leave_requests()

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
        print("7. Anuluj wniosek pracownika")
        print("8. Urlopy użytkownika")
        print("0. Wyloguj")

        choice = input("\nWybierz opcję: ").strip()

        if choice == "1":
            if not _check(role, "can_submit_request"):
                continue
            try:
                start = datetime.strptime(input("Data startu (YYYY-MM-DD): "), "%Y-%m-%d").date()
                end = datetime.strptime(input("Data końca  (YYYY-MM-DD): "), "%Y-%m-%d").date()
                days = int(input("Liczba dni urlopu: "))
                req = LeaveRequest(
                    user.user_id,
                    getattr(user, "first_name", user.username),
                    getattr(user, "last_name", ""),
                    start, end, days
                )
                new_id = max(leave_requests.keys(), default=0) + 1
                leave_requests[new_id] = req
                save_leave_requests(leave_requests)
                app_log.add_new_change(user.user_id, "dodaj", "leave_request")
                print(f"✓ Wniosek złożony. Status: {req.status.value}")
            except ValueError as e:
                print(f"Błąd danych: {e}")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "2":
            if not _check(role, "can_see_own_requests"):
                continue
            display_vacations(user.user_id)

        elif choice == "3":
            if not _check(role, "can_cancel_request"):
                continue
            # Manager anuluje swój własny wniosek
            my_requests = {rid: r for rid, r in leave_requests.items() if r.employee_id == user.user_id}
            req_id, req = _pick_request(my_requests)
            if req:
                try:
                    req.cancel_request(user.username, datetime.now())
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(user.user_id, "anuluj", "leave_request")
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "4":
            if not _check(role, "can_see_all_requests"):
                continue
            team_requests = {rid: r for rid, r in leave_requests.items() if r.employee_id != user.user_id}
            if not team_requests:
                print("Brak wniosków od innych pracowników.")
            else:
                print("\n=== Wnioski zespołu ===")
                for req_id, req in team_requests.items():
                    print(f"  [{req_id}] {req.first_name} {req.last_name} | "
                          f"{req.start_date} – {req.end_date} | "
                          f"Status: {req.status.value}")

        elif choice == "5":
            if not _check(role, "can_approve_request"):
                continue
            team_requests = {rid: r for rid, r in leave_requests.items() if r.employee_id != user.user_id}
            req_id, req = _pick_request(team_requests)
            if req:
                try:
                    req.approve(user.username)
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(user.user_id, "zatwierdz", "leave_request")
                    print("✓ Wniosek zatwierdzony.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "6":
            if not _check(role, "can_reject_request"):
                continue
            team_requests = {rid: r for rid, r in leave_requests.items() if r.employee_id != user.user_id}
            req_id, req = _pick_request(team_requests)
            if req:
                try:
                    req.rejected(user.username)
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(user.user_id, "odrzuc", "leave_request")
                    print("✓ Wniosek odrzucony.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "7":
            if not _check(role, "can_cancel_request"):
                continue
            # Manager anuluje cudzy wniosek
            team_requests = {rid: r for rid, r in leave_requests.items() if r.employee_id != user.user_id}
            req_id, req = _pick_request(team_requests)
            if req:
                try:
                    req.cancel_request(user.username, datetime.now())
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(user.user_id, "anuluj", "leave_request")
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "8":
            if not _check(role, "can_see_user_vacations"):
                continue
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
#  PANEL HR
# ──────────────────────────────────────────────

def hr_menu(user):
    role = user.role
    while True:
        leave_requests = load_leave_requests()

        print(f"\n=== Panel HR ({user.username}) ===")
        if hasattr(user, "get_leave_days"):
            print(f"Dostępne dni urlopu: {user.get_leave_days()} / {user.total_leave_days}")
        print("--- Moje wnioski ---")
        print("1. Złóż wniosek urlopowy")
        print("2. Moje urlopy")
        print("3. Anuluj swój wniosek")
        print("--- Wszystkie wnioski ---")
        print("4. Lista wszystkich wniosków")
        print("5. Anuluj wniosek pracownika")
        print("--- Użytkownicy ---")
        print("6. Lista użytkowników")
        print("7. Dodaj użytkownika")
        print("8. Urlopy użytkownika")
        print("0. Wyloguj")

        choice = input("\nWybierz opcję: ").strip()

        if choice == "1":
            if not _check(role, "can_submit_request"):
                continue
            try:
                start = datetime.strptime(input("Data startu (YYYY-MM-DD): "), "%Y-%m-%d").date()
                end = datetime.strptime(input("Data końca  (YYYY-MM-DD): "), "%Y-%m-%d").date()
                days = int(input("Liczba dni urlopu: "))
                req = LeaveRequest(
                    user.user_id,
                    getattr(user, "first_name", user.username),
                    getattr(user, "last_name", ""),
                    start, end, days
                )
                new_id = max(leave_requests.keys(), default=0) + 1
                leave_requests[new_id] = req
                save_leave_requests(leave_requests)
                app_log.add_new_change(user.user_id, "dodaj", "leave_request")
                print(f"✓ Wniosek złożony. Status: {req.status.value}")
            except ValueError as e:
                print(f"Błąd danych: {e}")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "2":
            if not _check(role, "can_see_own_requests"):
                continue
            display_vacations(user.user_id)

        elif choice == "3":
            if not _check(role, "can_cancel_request"):
                continue
            # HR anuluje swój własny wniosek
            my_requests = {rid: r for rid, r in leave_requests.items() if r.employee_id == user.user_id}
            req_id, req = _pick_request(my_requests)
            if req:
                try:
                    req.cancel_request(user.username, datetime.now())
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(user.user_id, "anuluj", "leave_request")
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "4":
            if not _check(role, "can_see_all_requests"):
                continue
            if not leave_requests:
                print("Brak wniosków urlopowych.")
            else:
                print("\n=== Wszystkie wnioski ===")
                for req_id, req in leave_requests.items():
                    print(f"  [{req_id}] {req.first_name} {req.last_name} | "
                          f"{req.start_date} – {req.end_date} | "
                          f"Status: {req.status.value} | "
                          f"Zatwierdził: {req.who_confirmed or '—'}")

        elif choice == "5":
            if not _check(role, "can_cancel_request"):
                continue
            # HR anuluje cudzy wniosek
            other_requests = {rid: r for rid, r in leave_requests.items() if r.employee_id != user.user_id}
            req_id, req = _pick_request(other_requests)
            if req:
                try:
                    req.cancel_request(user.username, datetime.now())
                    save_leave_requests(leave_requests)
                    app_log.add_new_change(user.user_id, "anuluj", "leave_request")
                    print("✓ Wniosek anulowany.")
                except Exception as e:
                    print(f"Błąd: {e}")

        elif choice == "6":
            if not _check(role, "can_list_users"):
                continue
            users = load_users()
            if not users:
                print("Brak użytkowników w bazie.")
            else:
                print("\n=== Użytkownicy ===")
                for uid, u in users.items():
                    status = "aktywny" if u.is_active else "nieaktywny"
                    print(f"  ID: {uid} | {u.username} | rola: {u.role} | {status}")

        elif choice == "7":
            if not _check(role, "can_add_user"):
                continue
            try:
                users = load_users()
                new_id = max(users.keys(), default=0) + 1
                username = input("Nazwa użytkownika: ").strip()
                password = input("Hasło (min. 6 znaków): ").strip()
                print("Role: Manager / HR / Worker")
                role_new = input("Rola: ").strip()
                new_user = create_user(new_id, username, password, role_new)
                app_log.add_new_change(user.user_id, "dodaj", f"user:{role_new}")
                print(f"✓ Użytkownik '{new_user.username}' (ID {new_user.user_id}) dodany.")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "8":
            if not _check(role, "can_see_user_vacations"):
                continue
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

    while True:
        print("\n*** Logowanie ***")
        username = input("Nazwa użytkownika: ").strip()
        password = input("Hasło: ").strip()

        user = login(username, password)

        if user is None:
            print("Niepoprawne dane logowania.")
            continue

        if isinstance(user, Admin):
            admin_menu(user)
        elif isinstance(user, Manager):
            manager_menu(user)
        elif isinstance(user, HR):
            hr_menu(user)
        elif isinstance(user, Worker):
            worker_menu(user)
        else:
            print("Nieznana rola — brak panelu.")


if __name__ == "__main__":
    start_app()
