
class LeaveRequest:
    def __init__(self,employee_id:int, first_name:str, last_name:str, start_date:str, end_date:str, amount_days:int, who_confirmed):
        """Klasa opisująca wniosek urlopowy pracownika"""
        self.employee_id = employee_id
        self.first_name = first_name
        self.last_name = last_name
        self.start_date = start_date
        self.end_date = end_date
        self.amount_days = amount_days
        self.status_leave = "pending" #pending - oczegujący na decyzję, approved/declined - decyzja
        if amount_days > 0: #TODO: wstawić pointer do pracownika i dostępnego czasu
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

