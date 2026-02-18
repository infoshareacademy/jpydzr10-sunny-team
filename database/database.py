import csv
import os
from typing import Dict
from models.user_employee import User
from models.role import Admin

DATA_FILE = "users.csv"

def load_users():
    """Wczytuje użytkowników z pliku CSV, jeśli taki plik istnieje"""
    if not os.path.exists(DATA_FILE):
        print(f'Plik nie istnieje {DATA_FILE}. Tworzę nową pustą bazę użytkowników')
        return {}

    users = Dict[int, User] = {}

    try:
        with open(DATA_FILE, 'r', encoding='utf-8', newline="") as f:
            reader = csv.reader(f)

            for row in reader:
                if len(row) < 4:
                    continue

            try:
                user_id = int(row[0])
                username = row[1]
                password_hash = row[2]
                role = row[3]

                if role == 'Admin':
                    user = Admin(user_id, username, password_hash)
                else:
                    user = User(user_id, username, password_hash, role)

                users[user_id] = user

            except (ValueError, IndexError) as e:
                print(f'Błąd w wierszu {row}: {e}')

    except Exception as e:
        print(f'Błąd podczas odczytu {DATA_FILE}: {e}')

    print(f'Wczytano {users} użytkowników z bazy')
    return users

def save_users():
    pass

def create_user(user_id: int, username: str ,password_hash: str , role: str):
    if role == "Admin":
        user = Admin(user_id,username,password_hash)
    else:
        user = User(user_id, username, password_hash, role)
    key = user.user_id

    user_database[key] = user

    return user

user_database = load_users()