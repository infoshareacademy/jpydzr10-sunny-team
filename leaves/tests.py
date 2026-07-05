from django.test import TestCase
from accounts.models import User
from leaves.models import WorkerProfile, LeaveRequest
from leaves.forms import LeaveRequestForm
from leaves.utils import Calendar_utils
from datetime import date, timedelta

class WorkerProfileTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        self.profile = WorkerProfile.objects.create(
            user = self.user,
            hire_date = date(2020,1,1),
            other_experience_days = 0,
            other_experience_years = 0,
            used_leave_days = 0,
            team = "A"
        )

    def test_get_leave_days(self):
        result = self.profile.get_leave_days()
        self.assertEqual(result, 22)

    def test_subtract_leave_days(self):
        result = self.profile.subtract_leave_days(5)
        self.assertEqual(self.profile.get_leave_days(),17)

    def test_subtract_0_leave_days(self):
        with self.assertRaises(ValueError):
            self.profile.subtract_leave_days(0)

    def test_subtract_999_leave_days(self):
        with self.assertRaises(ValueError):
            self.profile.subtract_leave_days(999)


class LeaveRequestSubmissionTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="pracownik", password="test1234")
        self.profile = WorkerProfile.objects.create(
            user=self.user,
            hire_date=date(2020, 1, 1),
            other_experience_days=0,
            other_experience_years=0,
            used_leave_days=0,
            team="A",
        )
        self.cal = Calendar_utils(date.today().year)

    def _find_n_working_days(self, n):
        """Zwraca (start, koniec) - n kolejnych dni roboczych zaczynając od jutra."""
        start = date.today() + timedelta(days=1)
        while not self.cal.is_working_day(start):
            start += timedelta(days=1)

        end = start
        counted = 1
        while counted < n:
            end += timedelta(days=1)
            if self.cal.is_working_day(end):
                counted += 1
        return start, end

    def test_poprawny_wniosek_ma_status_pending(self):
        start, end = self._find_n_working_days(2)

        form = LeaveRequestForm(
            data={"start_date": start, "end_date": end, "confirmed": "true"},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

        leave_request = form.save(commit=False)
        leave_request.employee = self.user
        leave_request.amount_days = form.cleaned_data["amount_days"]
        leave_request.save()

        self.assertEqual(leave_request.status, LeaveRequest.Status.PENDING)
        self.assertEqual(LeaveRequest.objects.count(), 1)

    def test_za_duzo_dni_wniosek_zostaje_odrzucony(self):
        # zakres znacznie przekraczający dostępny limit dni urlopowych (20-26 dni)
        year = date.today().year
        start = date(year, 8, 1)
        end = date(year, 12, 31)

        form = LeaveRequestForm(
            data={"start_date": start, "end_date": end, "confirmed": "true"},
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("przekracza aktualny limit urlopowy", str(form.errors))
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_end_date_wczesniejsza_niz_start_date_zwraca_blad(self):
        start = date.today() + timedelta(days=10)
        end = date.today() + timedelta(days=5)

        form = LeaveRequestForm(
            data={"start_date": start, "end_date": end, "confirmed": "true"},
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("nie może być późniejsza niż zakończenia", str(form.errors))
        self.assertEqual(LeaveRequest.objects.count(), 0)