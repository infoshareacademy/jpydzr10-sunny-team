from datetime import date
from _console_application.models.user import User
from _console_application.utils.date_utils import Calendar_utils
from dateutil.relativedelta import relativedelta

class Worker(User):
    def __init__(self, user_id: int, username: str, password_hash: str, first_name: str, last_name: str, hire_date: date, other_experience: tuple, used_leave_days: int, team: str, role = "Worker", is_active: bool = True): #total_leave_days: int,
        super().__init__(user_id, username, password_hash, role, is_active)
        self.first_name = first_name
        self.last_name = last_name
        self.hire_date = hire_date
        self.other_experience = other_experience #(years,days)
        self.total_leave_days = self._get_total_leave_days()
        self.used_leave_days = used_leave_days
        self.team = team

    def _total_experience_years(self): #
        return relativedelta(date.today(), self.hire_date - relativedelta(years=self.other_experience[0], days=self.other_experience[1])).years

    def _get_total_leave_days(self):
        k=Calendar_utils(date.today().year)
        return k.max_leave_days()[0] if self._total_experience_years() < 10 else k.max_leave_days()[1]

    def get_leave_days(self):
        return self.total_leave_days - self.used_leave_days

    def set_leave_days(self, new_value):
        if new_value <= 0 or new_value > self.total_leave_days:
            raise ValueError(f"New value is out of scope:{0} - {self.total_leave_days}")
            return
        self.used_leave_days = self.total_leave_days - new_value

    def reset_leave_days(self):
        self.used_leave_days = 0

    def subtract_leave_days(self, amount):
        if amount <= 0 or amount > self.total_leave_days - self.used_leave_days:
            raise ValueError(f"New value is out of scope:{0} - {self.total_leave_days - self.used_leave_days} (remaining leave days)")
            return
        self.used_leave_days = self.used_leave_days + amount

    def add_leave_days(self, amount):
        if amount <= 0:
            raise ValueError("amount of days must be positive non-zero number")
        self.used_leave_days = self.used_leave_days - amount

    def update_leave_days(self):
        ... # leaving empty, since I have no idea where new value would come from