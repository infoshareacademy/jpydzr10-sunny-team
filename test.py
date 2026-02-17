from auth.login import login, hash_password
from database.database import create_user, user_database

create_user(1, "ola", hash_password("haslo123"), "Admin")
create_user(2, "tomek", hash_password("qwertyui"), "Worker")
create_user(3, "asia",  hash_password("tajne123"), "User")

testy = [
    ("ola",   "haslo123",   "powinien się zalogować"),
    ("ola",   "zlehaslo",   "złe hasło → None"),
    ("tomek", "qwertyui",   "powinien się zalogować"),
    ("asia",  "tajne123",   "powinien się zalogować"),
    ("janek", "cokolwiek",  "nie istnieje → None"),
    ("",      "haslo123",   "pusty username → błąd walidacji"),
    ("ola",   "abcde",      "za krótkie hasło → błąd walidacji"),
    ("ola",   "123456",     "poprawne, ale inne hasło → None"),
    ("ola",   "",           "puste hasło → błąd walidacji"),
]

print("=== TESTY LOGOWANIA ===")

for username, password, opis in testy:
    wynik = login(username, password)

    if wynik is not None:
        print(f" {opis:.<35} → ZALOGOWANO: {wynik.username}")
    else:
        print(f" {opis:.<35} → NIE zalogowano")