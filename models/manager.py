from models.worker import Worker
from datetime import date

class Manager(Worker):
    def __init__(self, user_id: int, username: str, password_hash: str,first_name: str, last_name: str, hire_date: date, total_leave_days: int, used_leave_days: int, role = "Manager"):
        super().__init__(user_id, username, password_hash, first_name, last_name, hire_date, total_leave_days, used_leave_days, role)
