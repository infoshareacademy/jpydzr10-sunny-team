import hashlib
from database.database import load_users

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def login(username: str, password: str):
    validate_result = validate_login_data(username, password)

    if validate_result != 'OK':
        print(f"Błąd walidacji: {validate_result}")
        return None

    db = load_users()

    for user in db.values():
        if user.username == username and user.password_hash == hash_password(password):
            if not user.is_active:
                print("Konto jest nieaktywne. Skontaktuj się z administratorem.")
                return None
            return user

    return None

def validate_login_data(username: str, password: str):
    if not username:
        return 'Podaj nazwę użytkownika'
    if not password:
        return 'Podaj hasło'
    if len(password) < 6:
        return 'Hasło powinno zawierać minimum 6 znaków'
    return 'OK'
