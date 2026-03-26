from services.user_services import create_new_user, update_user, delete_user, list_all_users
from datetime import date

# Tworzenie użytkownika
create_new_user(
    user_id=10,
    username="jan.kowalski",
    password="tajne123",
    role="Worker",
    first_name="Jan",
    last_name="Kowalski",
    hire_date = date(2020, 6, 15),
    other_experience=(2,10),
    used_leave_days=5,
    team="IT"
)

# Aktualizacja hasła
update_user(10, password="nowehaslo456", team="HR")

# Usunięcie
delete_user(10)

# Lista wszystkich użytkowników
users = list_all_users()
for u in users.values():
    print(u.username, u.role)