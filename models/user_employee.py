from datetime import date

class User:
    """
    Reprezentuje konto użytkownika w systemie urlopowym.
    Zawiera dane potrzebne do logowania i kontroli dostępu.
    """
    def __init__(self, user_id: int, username: str ,password_hash: str , role: str):
        self.user_id = user_id
        self.username = username
        self.password_hash = password_hash
        self.role = role

class Employee(User):
    """
    Reprezentuje pracownika w systemie urlopowym.
    Zawiera dane kadrowe.
    """
    def __init__(self, user_id: int, username: str, password_hash: str, employee_id: int, first_name: str, last_name: str, hire_date: date, role: str):
        super().__init__(user_id, username, password_hash, role)
        self.employee_id = employee_id
        self.first_name = first_name
        self.last_name = last_name
        self.hire_date = hire_date

    def __str__(self):
        return f"id: {self.employee_id}\nimie i nazwisko: {self.first_name} {self.last_name}\ndata zatrudnienia: {self.hire_date}"

