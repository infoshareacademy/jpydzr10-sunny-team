import csv
import os
from datetime import datetime, date
from typing import Dict

from leave_requests.leave_request import LeaveRequest, LeaveStatus

DATA_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'startup', 'leave_requests.csv'))

def load_leave_requests() -> Dict[int, LeaveRequest]:
    """Wczytuje wnioski urlopowe z pliku CSV."""
    if not os.path.exists(DATA_FILE):
        print("Brak pliku wniosków urlopowych")
        return {}

    requests: Dict[int, LeaveRequest] = {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # pomijamy nagłówek

            for row in reader:
                try:
                    request_id = int(row[0])
                    employee_id = int(row[1])
                    first_name = row[2]
                    last_name = row[3]
                    start_date = datetime.strptime(row[4], "%Y-%m-%d").date()
                    end_date = datetime.strptime(row[5], "%Y-%m-%d").date()
                    days = int(row[6])
                    status = LeaveStatus[row[7]]  # używamy .name
                    who_confirmed = row[8] if row[8] else None

                    req = LeaveRequest(
                        employee_id,
                        first_name,
                        last_name,
                        start_date,
                        end_date,
                        days
                    )
                    req.status = status
                    req.who_confirmed = who_confirmed

                    requests[request_id] = req

                except Exception as e:
                    print(f"Błąd w wierszu {row}: {e}")

    except Exception as e:
        print(f"Błąd przy wczytywaniu {DATA_FILE}: {e}")

    print(f"Wczytano {len(requests)} wniosków z bazy")
    return requests


def save_leave_requests(requests: Dict[int, LeaveRequest]):
    """Zapisuje wszystkie wnioski urlopowe do CSV."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)

            writer.writerow([
                "request_id",
                "employee_id",
                "first_name",
                "last_name",
                "start_date",
                "end_date",
                "days",
                "status",
                "who_confirmed"
            ])

            for req_id, req in requests.items():
                writer.writerow([
                    req_id,
                    req.employee_id,
                    req.first_name,
                    req.last_name,
                    req.start_date.strftime("%Y-%m-%d"),
                    req.end_date.strftime("%Y-%m-%d"),
                    req.amount_days,
                    req.status.name,
                    req.who_confirmed if req.who_confirmed else ""
                ])

        print(f"Zapisano {len(requests)} wniosków do {DATA_FILE}")

    except Exception as e:
        print(f"Błąd zapisu do {DATA_FILE}: {e}")


def create_leave_request(requests: Dict[int, LeaveRequest], employee, start_date: date, end_date: date,
                         days: int) -> LeaveRequest:
    """Tworzy nowy wniosek urlopowy i zapisuje do CSV."""

    # Walidacja dni urlopu
    available_days = employee.total_leave_days - employee.used_leave_days
    if days > available_days:
        print(f"Uwaga: Wniosek przekracza dostępne dni urlopu ({available_days} dni). Wniosek zostanie odrzucony.")

    new_id = max(requests.keys(), default=0) + 1

    req = LeaveRequest(
        employee.user_id,
        employee.first_name,
        employee.last_name,
        start_date,
        end_date,
        days
    )

    requests[new_id] = req
    save_leave_requests(requests)

    return req