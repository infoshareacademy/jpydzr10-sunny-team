from datetime import date,datetime
from enum import Enum

class LeaveStatus(Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"
    canceled = "Canceled"

class LeaveRequest:

    def __init__(self,
                 employee_id:int,
                 first_name:str,
                 last_name:str,
                 start_date:date,
                 end_date:date,
                 amount_days:int):
        """Klasa opisująca wniosek urlopowy pracownika"""
        from _console_application.database.database import load_users

        self.employee_id = employee_id
        self.first_name = first_name
        self.last_name = last_name
        self.start_date = start_date
        self.end_date = end_date
        self.amount_days = amount_days

        self.status = LeaveStatus.pending
        user_list = load_users()
        if amount_days > user_list[employee_id].total_leave_days - user_list[employee_id].used_leave_days:
            self.status = LeaveStatus.rejected
        
        self.who_confirmed = None

    def approve(self,who_confirmed:str):
        self.status = LeaveStatus.approved
        self.who_confirmed = who_confirmed

    def rejected(self,who_confirmed:str):
        self.status = LeaveStatus.rejected
        self.who_confirmed = who_confirmed

    def change_request(self,new_start_date:date,new_end_date:date,new_amount_days:int):

        if self.status != LeaveStatus.pending:
            raise Exception("Można edytować tylko wniosek oczekujący!")

        if new_end_date < new_start_date:
            raise ValueError("Data końcowa nie może być przed początkową")

        self.start_date = new_start_date
        self.end_date = new_end_date
        self.amount_days = new_amount_days

    def cancel_request(self,canceled_by,canceled_at):
        if self.status != LeaveStatus.pending:
            raise Exception("Można anulować wniosek oczekujący")
        self.status = LeaveStatus.canceled
        self.canceled_by = canceled_by
        self.canceled_at = datetime.now()


    def __repr__(self):
        return(f"Request from {self.first_name} {self.last_name}: {self.start_date} - {self.end_date} ({self.amount_days} days)\n"
               f"Current status: {self.status}")
