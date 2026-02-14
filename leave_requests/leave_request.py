
class LeaveRequest:
    def __init__(self,employee_id:int, first_name:str, last_name:str, start_date:str, end_date:str, amount_days:int, who_confirmed):
        """Klasa opisująca wniosek urlopowy pracownika"""
        self.employee_id = employee_id
        self.first_name = first_name
        self.last_name = last_name
        self.start_date = start_date
        self.end_date = end_date
        self.amount_days = amount_days
        self.status_leave = False #jako odrzucony, True jako zatwierdzone
        self.who_confirmed = who_confirmed
        # self.status = status

    def confirmed_leave(self):
        self.status_leave = True

