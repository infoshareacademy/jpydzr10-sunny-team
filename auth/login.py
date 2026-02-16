import hashlib
from database.database import user_database

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def login(username: str, password: str):
    for user in user_database.values():
        if user.username == username and user.password_hash == hash_password(password):
            return user

    return None

