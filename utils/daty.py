# Tu trzymamy wszystko co związane z datami, urlopami, świętami

import calendar
from datetime import date, datetime, timedelta
import tempora

def is_working_day(dzien: date):
    if calendar.weekday(dzien.year, dzien.month, dzien.day) >= 5:
        return False
    return True

def is_weekend(dzien: date) :
    return dzien.weekday() >= 5

def date_format(d: date):
    return d.strftime("%d.%m.%Y (%a)")

def current_in_utc():
    """zwraca aktualny czas w UTC"""
    return datetime.now