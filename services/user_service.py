from models.admin import Admin
from auth.login import hash_password
from datetime import date
from models.worker import Worker
from database.database import save_users, user_database
from models.user import User
from database.workers_db import load_workers, save_workers


def require_admin(current_user):
    if not current_user or current_user.role != "Admin" or not current_user.is_active:
        raise PermissionError("Tylko admin może wykonać tę operację")


def create_user(current_user, user_id: int, username: str, password: str, role: str, is_active: bool = True):
    require_admin(current_user)
    password_hash = hash_password(password)

    if user_id in user_database:
        raise ValueError("User ID już istnieje")

    if role == "Admin":
        user = Admin(user_id, username, password_hash, is_active)

    elif role == "Worker":
        user = Worker(
            user_id=user_id,
            username=username,
            password_hash=password_hash,
            first_name="",
            last_name="",
            hire_date=date.today(),
            other_experience=(0, 0),
            used_leave_days=0,
            team="",
            is_active=is_active
        )

    else:
        user = User(user_id, username, password_hash, role, is_active)

    user_database[user_id] = user

    save_users() # Zapisujemy do bazy CSV nowego użytkownika
    return user


def get_user(current_user, user_id: int):
    require_admin(current_user)

    return user_database.get(user_id)


def get_all_users(current_user):
    require_admin(current_user)

    return list(user_database.values())


def update_user(current_user, user_id: int, **kwargs):
    require_admin(current_user)

    user = user_database.get(user_id)
    if not user:
        raise ValueError("User nie istnieje")

    if "username" in kwargs:
        user.username = kwargs["username"]

    if "password" in kwargs:
        from auth.login import hash_password
        user.password_hash = hash_password(kwargs["password"])

    if "is_active" in kwargs:
        user.is_active = kwargs["is_active"]

    save_users()
    return user


def deactivate_user(current_user, user_id: int):
    require_admin(current_user)

    user = user_database.get(user_id)
    if not user:
        raise ValueError("User nie istnieje")

    user.deactivate()
    save_users()

    return user


def change_user_role(current_user, user_id: int, new_role: str):
    require_admin(current_user)

    user = user_database.get(user_id)
    if not user:
        raise ValueError("User nie istnieje")

    old_role = user.role

    if old_role == new_role:
        return user  # nic się nie zmienia

    # zmiana NA worker
    if new_role == "Worker" and old_role != "Worker":
        worker = Worker(
            user_id=user.user_id,
            username=user.username,
            password_hash=user.password_hash,
            first_name="",
            last_name="",
            hire_date=date.today(),
            other_experience=(0, 0),
            used_leave_days=0,
            team="",
            is_active=user.is_active
        )

        user_database[user_id] = worker

    # zmiana Z worker
    if old_role == "Worker" and new_role != "Worker":
        workers = load_workers()
        workers.pop(user.user_id, None)
        save_workers(workers)

    user.role = new_role
    save_users()

    return user