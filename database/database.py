# Importy do CSV
import os
import csv
from typing import Dict

from models.user import User
from models.admin import Admin
from models.worker import Worker
import startup
from database.workers_db import load_workers

"""Scieżka do naszego pliku"""
DATA_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'startup', 'users.csv'))
# DATA_FILE = "startup/users.csv"     # Możecie zmienić, jeśli chcecie by plik był przechowywany gdzie indziej.
                            # Ewentualnie możemy utworzyć folder "Data" i tam przechowywać plik z bazą.

def load_users():
    """Wczytuje użytkowników z pliku CSV, jeśli taki plik istnieje"""

    workers_data = load_workers()

    if not os.path.exists(DATA_FILE):
        print(f'Plik nie istnieje {DATA_FILE}. Tworzę nową pustą bazę użytkowników')
        return {}

    users: Dict[int, User] = {}

    try:
        with open(DATA_FILE, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)

            # Pomijamy nagłówek, jako że to nie dane użytkowników (user_id, username, password_hash, role)
            next(reader, None)

            for row in reader:
                if len(row) < 4:
                    print(f'Pominięto niekompletny wiersz')
                    continue

                try:
                    user_id = int(row[0])
                    username = row[1]
                    password_hash = row[2]
                    role = row[3]

                    if role == 'Admin':
                        user = Admin(user_id, username, password_hash)

                    elif role == "Worker":
                        w = workers_data.get(user_id)

                        if not w:
                            print(f"Brak danych worker dla ID {user_id}")
                            continue

                        user = Worker(
                            user_id,
                            username,
                            password_hash,
                            w["first_name"],
                            w["last_name"],
                            w["hire_date"],
                            (w["other_experience_years"], w["other_experience_days"]),
                            w["used_leave_days"],
                            w["team"]
                        )

                    else:
                        user = User(user_id, username, password_hash, role)


                    users[user_id] = user

                except (ValueError, IndexError) as e:
                    print(f'Błąd w wierszu {row}: {e}')

    except Exception as e:
        print(f'Błąd podczas odczytu {DATA_FILE}: {e}')

    print(f'Wczytano {len(users)} użytkowników z bazy')
    return users

def save_users():
    """Zapisujemy nowych użytkowników do pliku CSV"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)

            # Tworzymy nagłówek by plik był bardziej czytelniejszy
            writer.writerow(['user_id', 'username', 'password_hash', 'role'])

            # Dane
            for user in sorted(user_database.values(), key=lambda u: u.user_id): # Sortujemy po user.id
                writer.writerow([
                    user.user_id,
                    user.username,
                    user.password_hash,
                    user.role
                ])
        print(f'Zapisano {len(user_database)} użytkowników do {DATA_FILE}')

    except Exception as e:
        print(f'Błąd zapisu do {DATA_FILE}: {e}')

user_database = load_users()

def create_user(user_id: int, username: str, password: str , role: str):

    from auth.login import hash_password

    password_hash = hash_password(password)

    if role == "Admin":
        user = Admin(user_id,username,password_hash)
    else:
        user = User(user_id, username, password_hash, role)

    key = user.user_id

    user_database[key] = user

    save_users() # Zapisujemy do bazy CSV nowego użytkownika
    return user