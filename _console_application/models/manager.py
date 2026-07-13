from _console_application.models.worker import Worker
from datetime import date

class Manager(Worker):
    def __init__(self, user_id: int, username: str, password_hash: str, first_name: str, last_name: str, hire_date: date, other_experience: tuple, used_leave_days: int, team: str = "", role="Manager", is_active: bool = True):
        super().__init__(user_id, username, password_hash, first_name, last_name, hire_date, other_experience, used_leave_days, team, role, is_active)
