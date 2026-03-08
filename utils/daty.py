"""Tu trzymamy wszystko co związane z datami, urlopami, świętami"""

import calendar
from datetime import date
import holidays

"""Odkomentowac jesli biblioteki tempora potrzebne"""
#import tempora

class Kalendarz: #Nie zmieniac nazwy klasy na 'Calendar', bo wtedy biblioteki Calendar zle dzialaja z jakiegos powodu.
    def __init__(self, year):
        self.year = year
        pl_holidays = holidays.PL(self.year)
        self.holidays = set(pl_holidays.keys())

    def is_working_day(self, d: date):
        if d.weekday() >= 5: #Usuwamy sobote i niedziele z listy dnich roboczych
            return False
        if self.is_holiday(d): #Usuwamy swieto z listy dnich roboczych.
            return False
        return True

    def is_weekend(self, d: date):
        return d.weekday() >= 5

    def is_holiday(self, d: date):
        return d in self.holidays

    def date_format(self, d: date):
        return d.strftime("%d.%m.%Y (%a)")

    def working_day_list(self, month):
        working_days = []
        for day in range(1, calendar.monthrange(self.year, month)[1] + 1):
            data = date(self.year, month, day)
            if self.is_working_day(data):
                working_days.append(data)
        return working_days