from datetime import date
from user import User

from leave_requests.leave_request import LeaveRequest

class Worker(User):
    def __init__(self, user_id: int, username: str, password_hash: str, first_name: str, last_name: str, hire_date: date, total_leave_days: int, used_leave_days: int, role = "Worker"):
        super().__init__(user_id, username, password_hash, role)
        self.first_name = first_name
        self.last_name = last_name
        self.hire_date = hire_date
        self.total_leave_days = total_leave_days
        self.used_leave_days = used_leave_days
        self.leave_requests_list = []

    def add_leave_request(self, leave_request: LeaveRequest):
        self.leave_requests_list.append(leave_request)

    def remove_leave_request(self,leave_request: LeaveRequest):
        self.leave_requests_list.remove(leave_request)

    def get_leave_requests(self):
        return self.leave_requests_list

