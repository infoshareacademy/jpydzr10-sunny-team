from auth.login import login
from admin_check import admin_exist
from models.admin import Admin
from leave_requests import leave_request

def admin_menu(admin,leave_requests):
    while True:
        print("Panel Admina.")
        print("1. Zatwierdź wniosek urlopowy")
        print("2. Odrzuć wniosek urlopowy")
        print("3. Anuluj wniosek urlopowy")
        print("4. Zmień wniosek urlopowy")
        print("0. Wyloguj")

        choice = input("Wybierz opcję: ")

        if choice == "1":
            req_id = int(input("ID wniosku: "))
            leave_requests[req_id].approve(admin.username)
            print("Wniosek zatwierdzony")

        elif choice == "2":
            req_id = int(input("ID wniosku: "))
            leave_requests[req_id].rejected(admin.username)
            print("Wniosek odrzucony")

        elif choice == "3":
            req_id = int(input("ID wniosku: "))
            leave_requests[req_id].cancel_request(admin.username, None)
            print("Wniosek anulowany")

        elif choice == "4":
            from datetime import datetime

            req_id = int(input("ID wniosku: "))

            new_start = datetime.strptime(input("Nowa data startu (YYYY-MM-DD): "), "%Y-%m-%d").date()
            new_end = datetime.strptime(input("Nowa data końca (YYYY-MM-DD): "), "%Y-%m-%d").date()
            days = int(input("Liczba dni: "))

            leave_requests[req_id].change_request(new_start, new_end, days)

            print("Wniosek zmieniony")

        elif choice == "0":
            print("Wylogowano")
            break

        else:
            print("Nieprawidłowa opcja")

def start_app():
    admin_exist()
    leave_requests = []
    while True:
        print("\n***Logowanie***")
        username = str(input("Podaj nazwę użytkownika: "))
        password = str(input("Podaj hasło: "))

        user = login(username,password)

        if user is None:
            print("Niepoprawne dane, zamykam program.")
            print("***Koniec***")
            continue

        if isinstance(user, Admin):
            admin_menu(user,leave_requests)
        else:
            print("Na razie tylko dla admina.")

if __name__ == "__main__":
    start_app()