import csv
import os
from datetime import datetime
from typing import Dict

from models.worker import Worker

DATA_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'startup', 'workers.csv')
)


def load_workers() -> Dict[int, Worker]:
    """
    Wczytuje pracowników z CSV jako obiekty Worker.
    UWAGA: username i password_hash są uzupełniane później w load_users()
    """
    workers: Dict[int, Worker] = {}

    if not os.path.exists(DATA_FILE):
        print("Brak pliku workers.csv")
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # pomijamy nagłówek

            for row in reader:
                try:
                    user_id = int(row[0])

                    worker = Worker(
                        user_id=user_id,
                        username="",  #uzupełni load_users()
                        password_hash="",
                        first_name=row[1],
                        last_name=row[2],
                        hire_date=datetime.strptime(row[3], "%Y-%m-%d").date(),
                        other_experience=(int(row[4]), int(row[5])),
                        used_leave_days=int(row[6]),
                        team=row[7]
                    )

                    workers[user_id] = worker

                except Exception as e:
                    print(f"Błąd w wierszu {row}: {e}")

    except Exception as e:
        print(f"Błąd odczytu workers.csv: {e}")

    print(f"Wczytano {len(workers)} pracowników")
    return workers


def save_workers(workers: Dict[int, Worker]):
    """
    Zapisuje pracowników (obiekty Worker) do CSV.
    """
    try:
        with open(DATA_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)

            writer.writerow([
                "user_id",
                "first_name",
                "last_name",
                "hire_date",
                "other_experience_years",
                "other_experience_days",
                "used_leave_days",
                "team"
            ])

            for w in workers.values():
                writer.writerow([
                    w.user_id,
                    w.first_name,
                    w.last_name,
                    w.hire_date.strftime("%Y-%m-%d"),
                    w.other_experience[0],
                    w.other_experience[1],
                    w.used_leave_days,
                    w.team
                ])

        print(f"Zapisano {len(workers)} pracowników")

    except Exception as e:
        print(f"Błąd zapisu workers.csv: {e}")


# def get_all_workers_from_users(user_database: Dict[int, Worker]) -> Dict[int, Worker]:
#     """Wyciąga wszystkich Workerów z user_database (jedyne źródło prawdy)."""
#     return {
#         user_id: user
#         for user_id, user in user_database.items()
#         if isinstance(user, Worker)
#     }
