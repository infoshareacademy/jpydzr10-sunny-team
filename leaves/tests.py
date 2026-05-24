from django.test import TestCase
from accounts.models import User
from leaves.models import WorkerProfile
from datetime import date

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
