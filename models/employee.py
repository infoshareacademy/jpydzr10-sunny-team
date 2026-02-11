from datetime import date

class Employee:
    """
    Reprezentuje pracownika w systemie urlopowym.
    Zawiera dane kadrowe i urlopowe.
    """
    def __init__(self, employee_id: int, first_name: str, last_name: str, hire_date: date, total_leave_days: int, used_leave_days: int):
        self.employee_id = employee_id
        self.first_name = first_name
        self.last_name = last_name
        self.hire_date = hire_date
        self.total_leave_days = total_leave_days
        self.used_leave_days = used_leave_days

    def remaining_leave_days(self):
        """
        Oblicza i zwraca liczbę pozostałych dni urlopu pracownika.
        :return:
        int: liczba dni urlopu, które pracownik jeszcze może wykorzystać
        """
        return self.total_leave_days - self.used_leave_days

    def get_hire_date(self):
        """
        Zwraca date zatrudnienia.
        :return:
        date: data zatrudnienia
        """
        return self.hire_date
