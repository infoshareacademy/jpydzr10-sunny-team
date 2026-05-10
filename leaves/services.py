from django.utils import timezone
from .utils import Calendar_utils
from datetime import datetime


def count_leave_days_service(start_str, end_str):
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date()

        now = timezone.now()
        today = now.date()
        current_year = now.year

        year_start = start_date.year
        year_end = end_date.year


        if start_date <= today or end_date <= today:
            raise ValueError("Nie można wybrać daty z przeszłości.")

        if start_date > end_date:
            raise ValueError("Data rozpoczęcia nie może być późniejsza niż zakończenia.")

        if year_start != current_year or year_end != current_year:
            raise ValueError(f"Wnioski można składać tylko na aktualny rok {current_year}.")

        cal = Calendar_utils(year_start)
        count = cal.count_leave_days(start_date, end_date)

        if int(count) <= 0:
            raise ValueError("Wybrany zakres nie obejmuje żadnych dni roboczych.")

        LIMIT_DNI = 26 #tymczaoswy limit bo nwm gdzie zapisany sa dostepne dni urlopowe workerow, WAŻNE DO POPRAWY

        if count > LIMIT_DNI:
            raise ValueError(
                f"Twój wniosek przekracza dostępny limit dni urlopowych: {LIMIT_DNI}."
            )

        return int(count)

    except ValueError as e:
        raise e