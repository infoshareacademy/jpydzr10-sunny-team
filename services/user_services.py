from typing import Optional, Dict
from database.database import user_database, save_users, create_user
from models.user import User
from models.admin import Admin
from models.worker import Worker
from database.workers_db import save_workers
from auth.login import hash_password


def create_new_user(user_id: int, username: str, password: str, role: str,
                    first_name: str = "", last_name: str = "", hire_date = None,
                    other_experience: tuple = (0,0), used_leave_days: int = 0,
                    team: str = "") -> User:
    """
    Tworzy nowego użytkownika i zapisuje go w bazie.
    Dla Workerów można podać dodatkowe dane personalne.
    """
    if role == "Worker":
        user = Worker(
            user_id=user_id,
            username=username,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            hire_date=hire_date,
            other_experience=other_experience,
            used_leave_days=used_leave_days,
            team=team
        )
        user_database[user_id] = user
    else:
        # Admin, HR, Manager
        user = create_user(user_id, username, password, role)

    save_users()
    return user

def get_user_by_id(user_id: int) -> Optional[User]:
    """Pobiera użytkownika po ID"""
    return user_database.get(user_id)

def update_user(user_id: int, **kwargs) -> Optional[User]:
    """
    Aktualizuje dane użytkownika.
    Można aktualizować: username, password, role, first_name, last_name, hire_date, team itd.
    """
    user = user_database.get(user_id)
    if not user:
        print(f"Użytkownik o ID {user_id} nie istnieje")
        return None

    # Aktualizacja podstawowych danych
    for key, value in kwargs.items():
        if key == "password":
            user.password_hash = hash_password(value)
        elif hasattr(user, key):
            setattr(user, key, value)
        else:
            print(f"Nieznane pole: {key}")

    save_users()
    return user

def delete_user(user_id: int) -> bool:
    """
    Usuwa użytkownika z bazy. Zwraca True jeśli usunięto, False jeśli użytkownik nie istnieje.
    """
    user = user_database.pop(user_id, None)
    if not user:
        print(f"Nie znaleziono użytkownika o ID {user_id}")
        return False

    # Jeśli to Worker, zapisujemy workers.csv
    if isinstance(user, Worker):
        workers = {u.user_id: u for u in user_database.values() if isinstance(u, Worker)}
        save_workers(workers)

    save_users()
    print(f"Usunięto użytkownika {user.username} (ID {user_id})")
    return True

def list_all_users() -> Dict[int, User]:
    """Zwraca słownik wszystkich użytkowników"""
    return user_database