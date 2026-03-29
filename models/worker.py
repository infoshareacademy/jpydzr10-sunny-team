from datetime import date
from user import User
from utils.daty import Kalendarz
from dateutil.relativedelta import relativedelta
from leave_requests.leave_request import LeaveRequest

class Worker(User):
    def __init__(self, user_id: int, username: str, password_hash: str, first_name: str, last_name: str, hire_date: date, other_experience: tuple, used_leave_days: int, team: str, role = "Worker"): #total_leave_days: int,
        super().__init__(user_id, username, password_hash, role)
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
        k=Kalendarz(date.today().year)
        return k.max_leave_days()[0] if self._total_experience_years() < 10 else k.max_leave_days()[1]

    def get_leave_days(self):
        return self.total_leave_days - self.used_leave_days
