import hashlib
from database.database import user_database

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def login(username: str, password: str):
    # Walidacja danych logowania. (Chcemy walidacje dopiero po znalezieniu użytkownika)
    validate_login_data(username, password)

    for user in user_database.values():
        if user.username == username and user.password_hash == hash_password(password):
            return user

    return None

# Walidacja danych logowania
def validate_login_data(username, password):
    if not username:
        raise ValueError('Username is required')

    if not password:
        raise ValueError('Password is required')

    if len(password) < 6:
        raise ValueError('Password must be at least 6 characters long')