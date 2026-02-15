from models.user_employee import User
from auth.login import AuthService
import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

users = [
    User(1,"ola", hash_password("12345"), "a"),
    User(2,"ala", hash_password("qwerty"),"b"),
    User(3,"marek", hash_password("Pa55w0rd"),"a"),
    User(4,"tomek", hash_password("4tepian"),"b"),
]

test = AuthService(users)

user_name = input("Podaj login: ")
password = input("Podaj hasło: ")

if test.login(user_name, password):
    print("Zalogowano!")
else:
    print("Błędne dane.")