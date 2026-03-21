import csv
import os
from datetime import datetime
from typing import Dict

DATA_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'startup', 'workers.csv'))


def load_workers() -> Dict[int, dict]:
    if not os.path.exists(DATA_FILE):
        print("Brak pliku workers.csv")
        return {}

    workers = {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)

            for row in reader:
                try:
                    user_id = int(row[0])

                    workers[user_id] = {
                        "first_name": row[1],
                        "last_name": row[2],
                        "hire_date": datetime.strptime(row[3], "%Y-%m-%d").date(),
                        "other_experience_years": int(row[4]),
                        "other_experience_days": int(row[5]),
                        "used_leave_days": int(row[6]),
                        "team": row[7]
                    }

                except Exception as e:
                    print(f"Błąd w wierszu {row}: {e}")

    except Exception as e:
        print(f"Błąd odczytu workers.csv: {e}")

    print(f"Wczytano {len(workers)} pracowników")
    return workers


def save_workers(workers: Dict[int, dict]):
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

            for user_id, w in workers.items():
                writer.writerow([
                    user_id,
                    w["first_name"],
                    w["last_name"],
                    w["hire_date"].strftime("%Y-%m-%d"),
                    w["other_experience_years"],
                    w["other_experience_days"],
                    w["used_leave_days"],
                    w["team"]
                ])

        print(f"Zapisano {len(workers)} pracowników")

    except Exception as e:
        print(f"Błąd zapisu workers.csv: {e}")


def create_worker(workers: dict, user_id: int, first_name: str, last_name: str,
                  hire_date, other_experience: tuple, used_leave_days: int, team:str):

    workers[user_id] = {
        "first_name": first_name,
        "last_name": last_name,
        "hire_date": hire_date,
        "other_experience_years": other_experience[0],
        "other_experience_days": other_experience[1],
        "used_leave_days": used_leave_days,
        "team": team
    }

    save_workers(workers)