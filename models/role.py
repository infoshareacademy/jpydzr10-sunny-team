from datetime import date
from models.user_employee import User, Employee


class Worker(Employee):
    def __init__(self, user_id: int, username: str, password_hash: str, employee_id: int, first_name: str, last_name: str, hire_date: date, total_leave_days: int, used_leave_days: int):
        super().__init__(user_id, username, password_hash, employee_id,first_name, last_name, hire_date, role = "Worker")
        self.total_leave_days = total_leave_days
        self.used_leave_days = used_leave_days

    def remaining_leave_days(self):
            """
            Oblicza i zwraca liczbę pozostałych dni urlopu pracownika.
            :return:
            int: liczba dni urlopu, które pracownik jeszcze może wykorzystać
            """
            return self.total_leave_days - self.used_leave_days

class Manager(Worker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = "Manager"

class HR(Worker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = "HR"

class Admin(User):
    def __init__(self, user_id: int, username: str, password_hash: str):
        super().__init__(user_id, username, password_hash, role="Admin")
