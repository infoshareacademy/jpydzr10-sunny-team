from datetime import date
from models.user import User
from utils.daty import Kalendarz
from dateutil.relativedelta import relativedelta

from leave_requests.leave_request import LeaveRequest

class Worker(User):
    def __init__(self, user_id: int, username: str, password_hash: str, first_name: str, last_name: str, hire_date: date, other_experience: tuple, used_leave_days: int, role = "Worker"): #total_leave_days: int,
        super().__init__(user_id, username, password_hash, role)
        self.first_name = first_name
        self.last_name = last_name
        self.hire_date = hire_date
        self.other_experience = other_experience #(years,days)
        self.total_leave_days = self._get_total_leave_days()
        self.used_leave_days = used_leave_days

    def _total_experience_years(self): #
        return relativedelta(date.today(), self.hire_date - relativedelta(years=self.other_experience[0], days=self.other_experience[1])).years

    def _get_total_leave_days(self):
        k=Kalendarz(date.today().year)
        return k.max_leave_days()[0] if self._total_experience_years() < 10 else k.max_leave_days()[1]

    def get_leave_days(self):
        return self.total_leave_days - self.used_leave_days

    def set_leave_days(self, new_value):
        if new_value <= 0 or new_value > self.total_leave_days:
            raise ValueError(f"Nowa wartość jest poza skalą: {0} - {self.total_leave_days}")
        self.used_leave_days = self.total_leave_days - new_value

    def reset_leave_days(self):
        self.used_leave_days = 0

    def subtract_leave_days(self, amount):
        if amount <= 0 or amount > self.total_leave_days - self.used_leave_days:
            raise ValueError(f"Nowa wartość jest poza skalą: {0} - {self.total_leave_days - self.used_leave_days} (remaining leave days)")
        self.used_leave_days = self.used_leave_days + amount

    def add_leave_days(self, amount):
        if amount <= 0:
            raise ValueError("Ilość dni musi być liczbą dodatnią")
        self.used_leave_days = self.used_leave_days - amount

    def update_leave_days(self):
        """Aktualizuje total_leave_days na podstawie aktualnego stażu pracy."""
        self.total_leave_days = self._get_total_leave_days()
    # --- Metody do obsługi wniosków urlopowych (przez CSV) ---

    def add_leave_request(self, leave_request):
        """Tworzy i zapisuje wniosek urlopowy do CSV."""
        from database.leave_requests_db import load_leave_requests, save_leave_requests
        requests = load_leave_requests()
        new_id = max(requests.keys(), default=0) + 1
        requests[new_id] = leave_request
        save_leave_requests(requests)

    def remove_leave_request(self, leave_request):
        """Usuwa wniosek urlopowy z CSV na podstawie zgodności danych."""
        from database.leave_requests_db import load_leave_requests, save_leave_requests
        requests = load_leave_requests()
        to_remove = None
        for req_id, req in requests.items():
            if (req.employee_id == leave_request.employee_id
                    and req.start_date == leave_request.start_date
                    and req.end_date == leave_request.end_date):
                to_remove = req_id
                break
        if to_remove is not None:
            del requests[to_remove]
            save_leave_requests(requests)

    def get_leave_requests(self):
        """Zwraca listę wniosków urlopowych tego pracownika z CSV."""
        from database.leave_requests_db import load_leave_requests
        requests = load_leave_requests()
        return [req for req in requests.values() if req.employee_id == self.user_id]