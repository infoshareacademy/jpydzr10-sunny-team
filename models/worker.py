from datetime import date
from user import User

class Worker(User):
    def __init__(self, user_id: int, username: str, password_hash: str, first_name: str, last_name: str, hire_date: date, total_leave_days: int, used_leave_days: int, role = "Worker"):
        super().__init__(user_id, username, password_hash, role)
        self.first_name = first_name
        self.last_name = last_name
        self.hire_date = hire_date
        self.total_leave_days = total_leave_days
        self.used_leave_days = used_leave_days
