from database.database import user_database
from models.worker import Worker

def show_my_leave_balance(user):
    """
    Wyświetla wykorzystane i pozostałe dni urlopu zalogowanego użytkownika.
    """
    if not isinstance(user, Worker):
        print("Brak danych urlopowych dla tej roli.")
        return

    print("\n===== Twój stan urlopu =====")
    print(f"Pracownik: {user.first_name} {user.last_name}")
    print(f"Całkowity urlop: {user.total_leave_days}")
    print(f"Wykorzystany urlop: {user.used_leave_days}")
    print(f"Pozostały urlop: {user.get_leave_days()}")
    print("=============================\n")

