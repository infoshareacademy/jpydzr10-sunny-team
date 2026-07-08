from django.urls import reverse
from accounts.models import User
from leaves.models import WorkerProfile, LeaveRequest
from leaves.forms import LeaveRequestForm
from leaves.utils import Calendar_utils
from datetime import date, timedelta
from django.test import TestCase

class WorkerProfileTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        self.profile = WorkerProfile.objects.create(
            user=self.user,
            hire_date=date(2020, 1, 1),
            other_experience_days=0,
            other_experience_years=0,
            used_leave_days=0,
            team="A",
        )

    def test_get_leave_days(self):
        result = self.profile.get_leave_days()
        self.assertEqual(result, 22)

    def test_subtract_leave_days(self):
        result = self.profile.subtract_leave_days(5)
        self.assertEqual(self.profile.get_leave_days(), 17)

    def test_subtract_0_leave_days(self):
        with self.assertRaises(ValueError):
            self.profile.subtract_leave_days(0)

    def test_subtract_999_leave_days(self):
        with self.assertRaises(ValueError):
            self.profile.subtract_leave_days(999)


class ViewsPermissionMatrixTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in ["Admin", "Manager", "HR", "Worker"]:
            cls.users[role] = User.objects.create_user(
                username=f"user_{role.lower()}",
                password="testpass123",
                role=role,
            )

        for role in ["Manager", "HR", "Worker"]:
            WorkerProfile.objects.create(
                user=cls.users[role],
                team="a",
                hire_date=date(2024, 1, 1),
            )

    def login_as(self, role):
        self.client.login(username=f"user_{role.lower()}", password="testpass123")

    def assert_forbidden_for_roles(self, url_name, forbidden_roles, allowed_roles, url_kwargs=None, expects_403=False):
        url = reverse(url_name, kwargs=url_kwargs or {})
        expected_forbidden_redirect = "/leaves/dashboard/"

        # 1. Niezalogowany -> redirect do loginu
        self.client.logout()
        response = self.client.get(url)
        try:
            login_url = reverse("login")
        except:
            login_url = "/accounts/login/"
        self.assertRedirects(response, f"{login_url}?next={url}", fetch_redirect_response=False)

        # 2. Zalogowany bez uprawnień
        for role in forbidden_roles:
            self.login_as(role)
            response = self.client.get(url)
            if expects_403:
                self.assertEqual(response.status_code, 403)
            else:
                self.assertRedirects(response, expected_forbidden_redirect)
            self.client.logout()

        # 3. Zalogowany z uprawnieniami
        for role in allowed_roles:
            self.login_as(role)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 200,
                f"[{url_name}] rola '{role}' powinna dostac status 200, otrzymano {response.status_code}"
            )
            self.client.logout()

    def test_all_requests_list_permissions(self):
        self.assert_forbidden_for_roles(
            "all_requests_list",
            forbidden_roles=["Worker"],
            allowed_roles=["Admin", "Manager", "HR"],
        )

    def test_my_vacations_permissions(self):
        self.assert_forbidden_for_roles(
            "my_vacations",
            forbidden_roles=["Admin", "HR", "Manager"],
            allowed_roles=["Worker"],
        )

    def test_add_user_permissions(self):
        self.assert_forbidden_for_roles(
            "add_user",
            forbidden_roles=["Manager", "Worker"],
            allowed_roles=["Admin", "HR"],
        )

    def test_reset_password_permissions(self):
        self.assert_forbidden_for_roles(
            "reset_password",
            forbidden_roles=["Manager", "Worker"],
            allowed_roles=["Admin", "HR"],
        )

    def test_team_leave_balance_permissions(self):
        self.assert_forbidden_for_roles(
            "team_leave_balance",
            forbidden_roles=["Worker", "Admin"],
            allowed_roles=["Manager", "HR"],
        )

    def test_export_requests_csv_permissions(self):
        self.assert_forbidden_for_roles(
            "export_requests_csv",
            forbidden_roles=["Worker"],
            allowed_roles=["Admin", "Manager", "HR"],
        )

    def test_team_calendar_permissions(self):
        self.assert_forbidden_for_roles(
            "team_calendar",
            forbidden_roles=["Worker"],
            allowed_roles=["Admin", "Manager", "HR"],
        )

    def test_log_history_permissions(self):
        self.assert_forbidden_for_roles(
            "log_history",
            forbidden_roles=["Worker"],
            allowed_roles=["Admin", "HR", "Manager"],
        )

    def test_leave_request_create_permissions(self):
        self.assert_forbidden_for_roles(
            "new_request",
            forbidden_roles=["Admin", "HR", "Manager"],
            allowed_roles=["Worker"],
            expects_403=True
        )

    def test_approve_request_permissions(self):
        pending = LeaveRequest.objects.create(
            employee=self.users["Worker"],
            start_date="2026-09-01",
            end_date="2026-09-05",
            amount_days=5,
            status=LeaveRequest.Status.PENDING,
        )
        url = reverse("approve_request", kwargs={"request_id": pending.pk})

        self.client.logout()
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.login_as("Worker")
        response = self.client.post(url)
        self.assertRedirects(response, "/leaves/dashboard/")
        self.client.logout()

        for role in ["Admin", "Manager", "HR"]:
            self.login_as(role)
            response = self.client.post(url)
            self.assertNotEqual(response.status_code, 403)
            self.client.logout()

    def test_reject_request_permissions(self):
        pending = LeaveRequest.objects.create(
            employee=self.users["Worker"],
            start_date="2026-09-10",
            end_date="2026-09-12",
            amount_days=3,
            status=LeaveRequest.Status.PENDING,
        )
        url = reverse("reject_request", kwargs={"request_id": pending.pk})

        self.client.logout()
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.login_as("Worker")
        response = self.client.post(url)
        self.assertRedirects(response, "/leaves/dashboard/")
        self.client.logout()

        for role in ["Admin", "Manager", "HR"]:
            self.login_as(role)
            response = self.client.post(url)
            self.assertNotEqual(response.status_code, 403)
            self.client.logout()

    def test_leave_request_update_permissions(self):
        pending = LeaveRequest.objects.create(
            employee=self.users["Worker"],
            start_date="2026-09-15",
            end_date="2026-09-16",
            amount_days=2,
            status=LeaveRequest.Status.PENDING,
        )
        url = reverse("leave_request_edit", kwargs={"pk": pending.pk})

        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        for role in ["Manager", "HR"]:
            self.login_as(role)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.client.logout()

        self.login_as("Admin")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.client.logout()

        self.login_as("Worker")
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, 200,
            f"Worker jako właściciel wniosku powinien móc go edytować (200), dostał: {response.status_code}"
        )
        self.client.logout()


class CancelLeaveViewPermissionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in ["Admin", "Manager", "HR", "Worker"]:
            cls.users[role] = User.objects.create_user(
                username=f"cancel_{role.lower()}",
                password="testpass123",
                role=role,
            )
        for role in ["Manager", "HR", "Worker"]:
            WorkerProfile.objects.create(
                user=cls.users[role],
                team="a",
                hire_date=date(2024, 1, 1),
            )

    def login_as(self, role):
        self.client.login(username=f"cancel_{role.lower()}", password="testpass123")

    def make_request(self, owner):
        return LeaveRequest.objects.create(
            employee=owner,
            start_date="2026-08-01",
            end_date="2026-08-05",
            amount_days=5,
            status=LeaveRequest.Status.PENDING,
        )

    def test_anonymous_cannot_cancel(self):
        leave_request = self.make_request(self.users["Worker"])
        url = reverse("leave_request_cancel", kwargs={"pk": leave_request.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    def test_roles_with_permission_are_not_forbidden(self):
        for role in ["Admin", "Worker"]:
            self.login_as(role)
            leave_request = self.make_request(self.users[role])
            url = reverse("leave_request_cancel", kwargs={"pk": leave_request.pk})
            response = self.client.post(url)
            self.assertNotEqual(response.status_code, 403)
            self.client.logout()

    def test_roles_without_permission_get_403(self):
        for role in ["Manager", "HR"]:
            self.login_as(role)
            leave_request = self.make_request(self.users[role])
            url = reverse("leave_request_cancel", kwargs={"pk": leave_request.pk})
            response = self.client.post(url)
            self.assertEqual(response.status_code, 403)
            self.client.logout()


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