# Importy do CSV
import os
import csv
from typing import Dict
from datetime import date
from models.user import User
from models.admin import Admin
"""Scieżka do naszego pliku"""
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "..", "startup", "users.csv")

def load_users():
    """Wczytuje użytkowników z pliku CSV, jeśli taki plik istnieje"""
    if not os.path.exists(DATA_FILE):
        print(f'Plik nie istnieje {DATA_FILE}. Tworzę nową pustą bazę użytkowników')
        return {}

    users: Dict[int, User] = {}

    try:
        with open(DATA_FILE, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get('user_id'):
                    print(f'Pominięto niekompletny wiersz')
                    continue

                try:
                    user_id = int(row['user_id'])
                    username = row['username']
                    password_hash = row['password_hash']
                    role = row['role']
                    if role == 'Admin':
                        user = Admin(user_id, username, password_hash)
                    elif role in ('Worker', 'Employee', 'HR', 'Manager'):
                        from models.worker import Worker
                        from models.hr import HR
                        from models.manager import Manager
                        first_name = row.get('first_name', '') or username
                        last_name = row.get('last_name', '') or ''
                        hire_date_str = row.get('hire_date', '')
                        hire_date = date.fromisoformat(hire_date_str) if hire_date_str else date.today()
                        other_experience = (
                            int(row.get('other_experience_years', 0) or 0),
                            int(row.get('other_experience_days', 0) or 0),
                        )
                        used_leave_days = int(row.get('used_leave_days', 0) or 0)
                        if role == 'HR':
                            user = HR(user_id, username, password_hash,
                                      first_name, last_name, hire_date,
                                      other_experience, used_leave_days)
                        elif role == 'Manager':
                            user = Manager(user_id, username, password_hash,
                                           first_name, last_name, hire_date,
                                           other_experience, used_leave_days)
                        else:
                            user = Worker(user_id, username, password_hash,
                                          first_name, last_name, hire_date,
                                          other_experience, used_leave_days)
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
            writer.writerow(['user_id', 'username', 'password_hash', 'role',
                             'first_name', 'last_name', 'hire_date',
                             'other_experience_years', 'other_experience_days',
                             'used_leave_days'])

            # Dane
            for user in sorted(user_database.values(), key=lambda u: u.user_id): # Sortujemy po user.id
                base = [user.user_id, user.username, user.password_hash, user.role]
                if hasattr(user, 'first_name'):
                    exp = user.other_experience
                    extra = [user.first_name, user.last_name,
                             user.hire_date.isoformat(),
                             exp[0], exp[1],
                             user.used_leave_days]
                else:
                    extra = ['', '', '', '', '', '']
                writer.writerow(base + extra)

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