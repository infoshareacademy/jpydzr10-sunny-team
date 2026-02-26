from auth.login import login
from database.database import create_user, user_database, save_users, load_users

user_database.clear()
user_database.update(load_users())

testy = [
    ("Admin",   "qwertyuiop",   "powinien się zalogować"),
    ("ola",   "zlehaslo",       "złe hasło -> None"),
    ("ola", "test123",          "powinien się zalogować"),
    ("tomek",  "123456789",     "powinien się zalogować"),
    ("kamil", "cokolwiek",      "nie istnieje -> None"),
    ("janek", "jakieshaslo123", "powinien się zalogować"),
    ("",      "haslo123",       "pusty username -> błąd walidacji"),
    ("ola",   "abcde",          "za krótkie hasło -> błąd walidacji"),
    ("ola",   "123456",         "poprawne, ale inne hasło -> None"),
    ("ola",   "",               "puste hasło -> błąd walidacji"),
]

print("=== TESTY LOGOWANIA Z PLIKU CSV ===")

for username, password, opis in testy:
    wynik = login(username, password)

    if wynik is not None:
        print(f" {opis:.<45} → ZALOGOWANO: {wynik.username}")
    else:
        print(f" {opis:.<45} → NIE zalogowano")