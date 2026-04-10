from datetime import date
from leave_requests.leave_request import LeaveRequest, LeaveStatus

"""Tymczasowa lista na potrzeby testów. Po utworzeniu akceptacji wniosków 
    i połączeniu pobierania danych z bazy danych lub pliku csv, poniższą liste trzeba zastąpić."""

vacations = [
    {"employee_id": 1, "start_date": date(2026, 3, 10), "end_date": date(2026, 5, 15), "status": "accepted"},
    {"employee_id": 1, "start_date": date(2026, 4, 5),  "end_date": date(2026, 4, 12), "status": "pending"},
    {"employee_id": 1, "start_date": date(2025, 12, 20),"end_date": date(2025, 12, 28),"status": "accepted"},
    {"employee_id": 1, "start_date": date(2026, 3, 10), "end_date": date(2026, 3, 16), "status": "rejected"},
    {"employee_id": 1, "start_date": date(2026, 12, 22), "end_date": date(2025, 12, 28), "status": "cancelled"},
    {"employee_id": 2, "start_date": date(2026, 3, 1),  "end_date": date(2026, 3, 7),  "status": "accepted"},
    {"employee_id": 2, "start_date": date(2026, 12, 20), "end_date": date(2025, 12, 28), "status": "accepted"},
    {"employee_id": 2, "start_date": date(2026, 11, 26), "end_date": date(2025, 12, 28), "status": "cancelled"},
]

def display_vacations(my_id):
    today = date.today() # Sprawdzamy dzisiejszą datę

    my_vacations = []
    for vacation in vacations:
        if vacation["employee_id"] == my_id: # Tworzymy listę urlopów na podstawie ID pracownika
            my_vacations.append(vacation)

    # Tworzymy puste listy (obecne, planowane, archiwalne)
    current = []
    planned = []
    old = []

    """ Sprawdzamy czy urlop już się rozpoczął i kiedy się kończy.
        Przykład start_date: 2026-03-10 - czyli już się rozpoczął, bo data dzisiaj jest 2026-03-13 
        więc wrzucany do listy current, jeśli end_date jest mniejszy od dzisiaj to wrzucamy do listy archiwalnej,
        jeśli start_date jeszcze ma nastąpić, to wrzucamy do listy planned || 
        tak wygląda przykładowy warunek: 10.03 ≤ 13.03 ≤ 15.05 """

    for vacation in my_vacations:
        if vacation["start_date"] <= today <= vacation["end_date"]:
            current.append(vacation)
        elif vacation["start_date"] > today:
            planned.append(vacation)
        else:
            old.append(vacation)

    # Wypisujemy urlopy na podstawie ID pracownika
    print("=====================================")
    print(f"Your vacations - Employee ID: {my_id}")
    print("=====================================")

    print("\nNow (current):")
    if len(current) == 0:
        print("None")
    else:
        for vacation in current:
            print("od", vacation["start_date"], "do", vacation["end_date"], " Status:", vacation["status"])

    print("\nPlanned:")
    if len(planned) == 0:
        print("None")
    else:
        for vacation in planned:
            print("od", vacation["start_date"], "do", vacation["end_date"], " Status:", vacation["status"])

    print("\nOld (finished/archived):")
    if len(old) == 0:
        print("None")
    else:
        for vacation in old:
            print("od", vacation["start_date"], "do", vacation["end_date"], " Status:", vacation["status"])

    print("=====================================")

# przykładowe wywołanie (ID pracownika 1)
if __name__ == "__main__":
    display_vacations(1)
