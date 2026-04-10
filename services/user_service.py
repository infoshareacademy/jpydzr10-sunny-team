from auth.login import hash_password
from datetime import date
from models.worker import Worker
from database.database import save_users, user_database
from models.user import User

def require_admin(current_user):
    if not current_user or current_user.role != "Admin" or current_user.is_active != True:
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
    save_users()

    return user


def get_user(current_user, user_id: int):
    require_admin(current_user)

    return user_database.get(user_id)


def get_all_users(current_user):
    require_admin(current_user)

    return list(user_database.values())
