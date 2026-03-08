from database.database import load_users

class LeaveRequest:
    def __init__(self,employee_id:int, first_name:str, last_name:str, start_date:str, end_date:str, amount_days:int):
        """Klasa opisująca wniosek urlopowy pracownika"""
        self.employee_id = employee_id
        self.first_name = first_name
        self.last_name = last_name
        self.start_date = start_date
        self.end_date = end_date
        self.amount_days = amount_days
        self.status_leave = "pending" #pending - oczegujący na decyzję, approved/declined - decyzja
        user_list = load_users()
        if amount_days < user_list[employee_id].total_leave_days - user_list[employee_id].used_leave_days:
            self.status_leave = "declined"
        # self.who_confirmed = who_confirmed
        # self.who_declined = who_declined
        # self.status = status

    def confirmed_leave(self,who_confirmed):
        self.status_leave = "approved"
        self.who_confirmed = who_confirmed

    def declined_leave(self,who_declined):
        self.status_leave = "declined"
        self.who_declined = who_declined

