"""Tu trzymamy wszystko co związane z datami, urlopami, świętami"""

import calendar
from datetime import date

"""Odkomentowac jesli biblioteki tempora potrzebne"""
#import tempora

def is_working_day(d: date):
    if d.weekday() >= 5: #Usuwamy sobote i niedziele z listy dnich roboczych
        return False
    return True

def is_weekend(d: date):
    return d.weekday() >= 5

def date_format(d: date):
    return d.strftime("%d.%m.%Y (%a)")

def working_day_list(self, month):
    working_days = []
    for day in range(1, calendar.monthrange(self.year, month)[1] + 1):
        data = date(self.year, month, day)
        if self.is_working_day(data):
            working_days.append(data)
    return working_days