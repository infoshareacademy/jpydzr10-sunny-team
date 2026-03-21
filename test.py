# from auth.login import login
# from database.database import create_user, user_database, save_users, load_users
#
# user_database.clear()
# user_database.update(load_users())
#
# testy = [
#     ("Admin",   "qwertyuiop",   "powinien się zalogować"),
#     ("ola",   "zlehaslo",       "złe hasło -> None"),
#     ("ola", "test123",          "powinien się zalogować"),
#     ("tomek",  "123456789",     "powinien się zalogować"),
#     ("kamil", "cokolwiek",      "nie istnieje -> None"),
#     ("janek", "jakieshaslo123", "powinien się zalogować"),
#     ("",      "haslo123",       "pusty username -> błąd walidacji"),
#     ("ola",   "abcde",          "za krótkie hasło -> błąd walidacji"),
#     ("ola",   "123456",         "poprawne, ale inne hasło -> None"),
#     ("ola",   "",               "puste hasło -> błąd walidacji"),
# ]
#
# print("=== TESTY LOGOWANIA Z PLIKU CSV ===")
#
# for username, password, opis in testy:
#     wynik = login(username, password)
#
#     if wynik is not None:
#         print(f" {opis:.<45} → ZALOGOWANO: {wynik.username}")
#     else:
#         print(f" {opis:.<45} → NIE zalogowano")
#

from datetime import date
from database import database, workers_db

# 1️⃣ Wczytujemy istniejących pracowników
workers_data = workers_db.load_workers()
users_data = database.load_users()

# 2️⃣ Parametry nowego pracownika
user_id = 101
username = "alojzy.noga"
password = "tajnehaslo"
first_name = "Alex"
last_name = "Kurzałapka"
hire_date = date(2020, 6, 15)
other_experience = (2, 120)  # 2 lata i 120 dni doświadczenia
used_leave_days = 5

# 3️⃣ Dodajemy do workers.csv
workers_db.create_worker(
    workers=workers_data,
    user_id=user_id,
    first_name=first_name,
    last_name=last_name,
    hire_date=hire_date,
    other_experience=other_experience,
    used_leave_days=used_leave_days
)

# 4️⃣ Tworzymy obiekt Worker w pamięci i dodajemy do user_database
worker_user = database.Worker(
    user_id=user_id,
    username=username,
    password_hash="jakieś_hasło",  # w realnym użyciu użyj database.create_user() z hasłem
    first_name=first_name,
    last_name=last_name,
    hire_date=hire_date,
    other_experience=other_experience,
    used_leave_days=used_leave_days
)

database.user_database[user_id] = worker_user

# 5️⃣ Zapis do users.csv
database.save_users()

print(f"Dodano Workera: {worker_user.first_name} {worker_user.last_name}")