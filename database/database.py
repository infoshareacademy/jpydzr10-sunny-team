# Importy do CSV
import os
import csv
from typing import Dict

from models.user import User
from models.admin import Admin
from models.worker import Worker
from models.hr import HR
from models.manager import Manager
from database.workers_db import load_workers, save_workers

"""Scieżka do naszego pliku"""
DATA_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'startup', 'users.csv'))

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
            next(reader, None)  # pomijamy nagłówek

            for row in reader:
                if len(row) < 5:
                    print(f'Pominięto niekompletny wiersz')
                    continue

                try:
                    user_id = int(row[0])
                    username = row[1]
                    password_hash = row[2]
                    role = row[3]
                    is_active = bool(int(row[4]))

                    if role == 'Admin':
                        user = Admin(user_id, username, password_hash, is_active=is_active)

                    elif role in ('Worker', 'HR', 'Manager'):
                        w = workers_data.get(user_id)

                        if not w:
                            print(f"Brak danych worker dla ID {user_id}")
                            continue

                        kwargs = dict(
                            user_id=user_id,
                            username=username,
                            password_hash=password_hash,
                            first_name=w.first_name,
                            last_name=w.last_name,
                            hire_date=w.hire_date,
                            other_experience=w.other_experience,
                            used_leave_days=w.used_leave_days,
                            team=w.team,
                            is_active=is_active,
                        )

                        if role == 'HR':
                            user = HR(**kwargs)
                        elif role == 'Manager':
                            user = Manager(**kwargs)
                        else:
                            user = Worker(**kwargs)

                    else:
                        user = User(user_id, username, password_hash, role, is_active)

                    users[user_id] = user

                except (ValueError, IndexError) as e:
                    print(f'Błąd w wierszu {row}: {e}')

    except Exception as e:
        print(f'Błąd podczas odczytu {DATA_FILE}: {e}')

    print(f'Wczytano {len(users)} użytkowników z bazy')
    return users


def save_users():
    """Zapisujemy użytkowników do pliku CSV"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'username', 'password_hash', 'role', 'is_active'])

            for user in sorted(user_database.values(), key=lambda u: u.user_id):
                writer.writerow([
                    user.user_id,
                    user.username,
                    user.password_hash,
                    user.role,
                    int(user.is_active)
                ])

            # Zapisujemy workers.csv dla Worker, HR i Manager (wszystkich dziedziczących po Worker)
            workers = {u.user_id: u for u in user_database.values() if isinstance(u, Worker)}
            save_workers(workers)

        print(f'Zapisano {len(user_database)} użytkowników do {DATA_FILE}')

    except Exception as e:
        print(f'Błąd zapisu do {DATA_FILE}: {e}')


user_database = load_users()


def create_user(user_id: int, username: str, password: str, role: str, is_active: bool = True):
    from auth.login import hash_password
    from datetime import date

    password_hash = hash_password(password)

    if role == 'Admin':
        user = Admin(user_id, username, password_hash, is_active=is_active)

    elif role in ('Worker', 'HR', 'Manager'):
        kwargs = dict(
            user_id=user_id,
            username=username,
            password_hash=password_hash,
            first_name="",
            last_name="",
            hire_date=date.today(),
            other_experience=(0, 0),
            used_leave_days=0,
            team="",
            is_active=is_active,
        )
        if role == 'HR':
            user = HR(**kwargs)
        elif role == 'Manager':
            user = Manager(**kwargs)
        else:
            user = Worker(**kwargs)

    else:
        user = User(user_id, username, password_hash, role, is_active)

    user_database[user.user_id] = user
    save_users()
    return user
