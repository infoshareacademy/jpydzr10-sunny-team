from datetime import datetime
import csv
import os

# Ścieżka absolutna - zawsze obok tego pliku w katalogu logs_old/
FILEPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'log_history.csv'))


def read_csv(filepath):
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        print(f"Plik {filepath} nie istnieje lub jest pusty.")
        return []
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def create_record(filepath, new_record: dict):
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    if file_exists:
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
    else:
        fieldnames = list(new_record.keys())
        rows = []

    rows.append(new_record)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Dodano nowy rekord {new_record}")


def update_record(filepath, record_id: str, updated_fields: dict):
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        print(f"Plik {filepath} nie istnieje lub jest pusty.")
        return
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    updated = False
    for row in rows:
        if row["user_id"] == record_id:
            row.update(updated_fields)
            updated = True
            break
    if not updated:
        print(f"Nie znaleziono rekordu z id {record_id}.")
        return

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Zaktualizowano rekord id={record_id}: {updated_fields}.")


def delete_record(filepath, record_id: str):
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        print(f"Plik {filepath} nie istnieje lub go nie znaleziono.")
        return

    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = [row for row in reader if row["user_id"] != record_id]

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Usunięto rekord id={record_id}.")


class ChangeLog:
    """
    user_id     - numer użytkownika w bazie
    action      - akcja: dodaj / usun / edytuj / zatwierdz / odrzuc / anuluj / reset_hasla
    object_type - obiekt: user / leave_request / password
    date        - kiedy wykonano
    """
    def __init__(self, user_id, action, object_type):
        self.user_id = user_id
        self.action = action
        self.object_type = object_type
        self.date = datetime.now()

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "action": self.action,
            "object_type": self.object_type,
            "date": self.date.strftime('%Y-%m-%d %H:%M:%S')
        }


class LogHistory:
    def __init__(self, filepath=FILEPATH):
        self.filepath = filepath
        self.log_history = []

    def add_new_change(self, user_id, action, object_type):
        new_log = ChangeLog(user_id, action, object_type)
        self.log_history.append(new_log)
        create_record(self.filepath, new_log.to_dict())

    def get_all_logs(self):
        """Zwraca wszystkie logi z pliku."""
        return read_csv(self.filepath)


# Globalna instancja używana w całej aplikacji
app_log = LogHistory()


if __name__ == '__main__':
    log = LogHistory()
    log.add_new_change(user_id='1', action='dodaj', object_type='user')
    log.add_new_change(user_id='2', action='usun', object_type='admin')
    log.add_new_change(user_id='3', action='edytuj', object_type='manager')

    print("\n--- Wszystkie logi ---")
    for record in log.get_all_logs():
        print(record)

    update_record(FILEPATH, record_id='2', updated_fields={'action': 'zablokuj'})
    delete_record(FILEPATH, record_id='3')
