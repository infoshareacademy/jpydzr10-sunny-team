import hashlib
from database.database import user_database

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def login(username: str, password: str):
    validate_result = validate_login_data(username, password) # Walidacja danych przed znalezieniem użytkownika w bazie danych.

    if validate_result != 'OK':
        print(f"Błąd walidacji: {validate_result}")
        return None

    for user in user_database.values():
        if user.username == username and user.password_hash == hash_password(password):
            return user

    return None

# Walidacja danych logowania
def validate_login_data(username: str, password: str):
    if not username:
        return 'Podaj nazwę użytkownika'
    if not password:
        return 'Podaj hasło'
    if len(password) < 6:
        return 'Hasło powinno zawierać minimum 6 znaków'

    return 'OK'