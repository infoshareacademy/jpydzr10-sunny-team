from auth.login import login, hash_password
from database.database import create_user, user_database

create_user(1, "ola", hash_password("12345"), "Admin")
create_user(2, "tomek", hash_password("abc"), "Worker")
user1 = login("ola", "12345")
user2 = login("tomek", "12345")

if user1:
    print("Zalogowano:", user1.username)
else:
    print("Błędne dane!")

if user2:
    print("Zalogowano:", user2.username)
else:
    print("Błędne dane!")