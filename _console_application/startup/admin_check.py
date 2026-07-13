from _console_application.models.admin import Admin
from _console_application.database.database import user_database,create_user

def admin_exist():
    if not (any(isinstance(user,Admin) for user in user_database.values())):
        print("Brak admina w bazie danych. Tworzenie SuperAdmina.")
        create_user(1,"SuperAdmin","123456","Admin")
