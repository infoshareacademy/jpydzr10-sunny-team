from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from leaves.models import WorkerProfile, LeaveRequest
from leaves.forms import LeaveRequestForm
from leaves.utils import Calendar_utils
from logs.models import AuthLog
from datetime import date, timedelta

class WorkerProfileTest(TestCase):
    def setUp(self):
        # Przygotowanie instancji użytkownika i jego profilu pracowniczego do testów
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
        # Sprawdzenie, czy bazowa liczba dni urlopowych wylicza się poprawnie (oczekiwane 22 dni)
        result = self.profile.get_leave_days()
        self.assertEqual(result, 22)

    def test_subtract_leave_days(self):
        # Sprawdzenie poprawnego odliczania dni urlopowych po pobraniu urlopu
        result = self.profile.subtract_leave_days(5)
        self.assertEqual(self.profile.get_leave_days(), 17)

    def test_subtract_0_leave_days(self):
        # Sprawdzenie, czy próba odjęcia 0 dni rzuca błąd walidacji
        with self.assertRaises(ValueError):
            self.profile.subtract_leave_days(0)

    def test_subtract_999_leave_days(self):
        # Sprawdzenie, czy próba odjęcia zbyt dużej liczby dni rzuca błąd walidacji
        with self.assertRaises(ValueError):
            self.profile.subtract_leave_days(999)


"""
Testy egzekwowania uprawnień.

Zakres: dla KAŻDEGO widoku chronionego przez `role_required` /
`RoleRequiredMixin` sprawdzamy:
  - rola BEZ danego uprawnienia -> redirect na 'dashboard' (302)
  - rola Z danym uprawnieniem   -> NIE redirect na 'dashboard'
  - użytkownik niezalogowany    -> 302 (redirect do loginu), nigdy 500

Dodatkowo weryfikujemy, że odmowa dostępu tworzy wpis w AuthLog
(action='access_denied_403'), zgodnie z RoleRequiredMixin / role_required.
"""

class ViewsPermissionMatrixTestCase(TestCase):
    """
    Dla widoków opartych o GET sprawdza pełną macierz: role z uprawnieniem
    -> NIE redirect na dashboard, role bez uprawnienia -> redirect na dashboard,
    niezalogowany -> 302 (redirect do loginu).
    """

    @classmethod
    def setUpTestData(cls):
        # Tworzenie testowych użytkowników dla każdej roli w systemie
        cls.users = {}
        for role in ["Admin", "Manager", "HR", "Worker"]:
            cls.users[role] = User.objects.create_user(
                username=f"user_{role.lower()}",
                password="testpass123",
                role=role,
            )

        # Tworzenie profili pracowniczych niezbędnych dla logiki widoków zależnych od zespołów
        for role in ["Manager", "HR", "Worker"]:
            WorkerProfile.objects.create(
                user=cls.users[role],
                team="a",
                hire_date=date(2024, 1, 1),
            )

    def login_as(self, role):
        # Metoda pomocnicza logująca użytkownika o wskazanej roli
        self.client.login(username=f"user_{role.lower()}", password="testpass123")

    def assert_forbidden_for_roles(self, url_name, forbidden_roles, allowed_roles, url_kwargs=None):
        """
        Uniwersalna metoda sprawdzająca dostęp:
          - gość -> redirect do loginu (302), nigdy 500
          - rola bez uprawnień -> redirect na 'dashboard' + wpis w AuthLog
          - rola z uprawnieniami -> NIE redirect na 'dashboard'
        """
        url = reverse(url_name, kwargs=url_kwargs or {})
        dashboard_url = reverse('dashboard')

        # niezalogowany -> redirect do loginu, nigdy 403/500
        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, 302,
            f"[{url_name}] anonimowy użytkownik powinien dostać redirect do loginu, "
            f"otrzymano {response.status_code}",
        )

        for role in forbidden_roles:
            self.login_as(role)
            logs_before = AuthLog.objects.filter(action='access_denied_403').count()

            response = self.client.get(url)

            self.assertEqual(
                response.status_code, 302,
                f"[{url_name}] rola '{role}' bez uprawnień powinna dostać redirect, "
                f"otrzymano {response.status_code}",
            )
            self.assertEqual(
                response.url, dashboard_url,
                f"[{url_name}] rola '{role}' bez uprawnień powinna być przekierowana "
                f"na dashboard, otrzymano redirect na {response.url}",
            )

            logs_after = AuthLog.objects.filter(action='access_denied_403').count()
            self.assertEqual(
                logs_after, logs_before + 1,
                f"[{url_name}] odmowa dostępu dla roli '{role}' powinna utworzyć wpis "
                f"w AuthLog (action='access_denied_403')",
            )

            self.client.logout()

        for role in allowed_roles:
            self.login_as(role)
            response = self.client.get(url)
            if response.status_code == 302:
                self.assertNotEqual(
                    response.url, dashboard_url,
                    f"[{url_name}] rola '{role}' z uprawnieniami nie powinna być "
                    f"przekierowana na dashboard",
                )
            self.client.logout()

    # --- can_see_all_requests --- (True: Admin, Manager, HR / False: Worker)
    def test_all_requests_list_permissions(self):
        # Test dostępu do pełnej listy wniosków (tylko Admin, Manager, HR)
        self.assert_forbidden_for_roles(
            "all_requests_list",
            forbidden_roles=["Worker"],
            allowed_roles=["Admin", "Manager", "HR"],
        )

    # --- can_see_own_requests --- (True: Worker / False: Admin, HR, Manager)
    def test_my_vacations_permissions(self):
        # Test widoku własnych wniosków urlopowych (tylko Worker)
        self.assert_forbidden_for_roles(
            "my_vacations",
            forbidden_roles=["Admin", "HR", "Manager"],
            allowed_roles=["Worker"],
        )

    # --- can_see_team_balance --- (True: Admin, Manager, HR / False: Worker)
    def test_team_leave_balance_permissions(self):
        # Test dostępu do podglądu stanu limitów urlopowych zespołu (Admin, Manager, HR)
        self.assert_forbidden_for_roles(
            "team_leave_balance",
            forbidden_roles=["Worker"],
            allowed_roles=["Admin", "Manager", "HR"],
        )

    # --- can_export_requests --- (True: Admin, Manager, HR / False: Worker)
    def test_export_requests_csv_permissions(self):
        # Test uprawnień do eksportu wniosków do pliku CSV (Admin, Manager, HR)
        self.assert_forbidden_for_roles(
            "export_requests_csv",
            forbidden_roles=["Worker"],
            allowed_roles=["Admin", "Manager", "HR"],
        )

    # --- can_see_team_calendar --- (True: Admin, Manager, HR / False: Worker)
    def test_team_calendar_permissions(self):
        # Test dostępu do widoku kalendarza zespołowego (Admin, Manager, HR)
        self.assert_forbidden_for_roles(
            "team_calendar",
            forbidden_roles=["Worker"],
            allowed_roles=["Admin", "Manager", "HR"],
        )


    # --- can_submit_request (CBV) --- (True: Worker / False: Admin, HR, Manager)
    def test_leave_request_create_permissions(self):
        # Test dostępu do formularza składania nowego wniosku urlopowego (tylko Worker)
        self.assert_forbidden_for_roles(
            "new_request",
            forbidden_roles=["Admin", "HR", "Manager"],
            allowed_roles=["Worker"],
        )

    # --- can_approve_request --- (True: Admin, Manager, HR / False: Worker)
    def test_approve_request_permissions(self):
        # Test akceptacji wniosku (POST) – Worker dostaje redirect na dashboard,
        # kadra zarządzająca przechodzi pomyślnie (redirect na all_requests_list)
        pending = LeaveRequest.objects.create(
            employee=self.users["Worker"],
            start_date="2026-09-01",
            end_date="2026-09-05",
            amount_days=5,
            status=LeaveRequest.Status.PENDING,
        )
        url = reverse("approve_request", kwargs={"request_id": pending.pk})
        dashboard_url = reverse('dashboard')

        self.client.logout()
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.login_as("Worker")
        logs_before = AuthLog.objects.filter(action='access_denied_403').count()
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, dashboard_url,
            f"[approve_request] rola 'Worker' bez uprawnień powinna być przekierowana "
            f"na dashboard, otrzymano redirect na {response.url}",
        )
        self.assertEqual(
            AuthLog.objects.filter(action='access_denied_403').count(), logs_before + 1,
        )
        self.client.logout()

        for role in ["Admin", "Manager", "HR"]:
            self.login_as(role)
            response = self.client.post(url)
            if response.status_code == 302:
                self.assertNotEqual(
                    response.url, dashboard_url,
                    f"[approve_request] rola '{role}' z uprawnieniami nie powinna być "
                    f"przekierowana na dashboard",
                )
            self.client.logout()

    # --- can_reject_request --- (True: Admin, Manager, HR / False: Worker)
    def test_reject_request_permissions(self):
        # Test odrzucenia wniosku (POST) – Worker dostaje redirect na dashboard,
        # Admin/Manager/HR mają dostęp
        pending = LeaveRequest.objects.create(
            employee=self.users["Worker"],
            start_date="2026-09-10",
            end_date="2026-09-12",
            amount_days=3,
            status=LeaveRequest.Status.PENDING,
        )
        url = reverse("reject_request", kwargs={"request_id": pending.pk})
        dashboard_url = reverse('dashboard')

        self.client.logout()
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.login_as("Worker")
        logs_before = AuthLog.objects.filter(action='access_denied_403').count()
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, dashboard_url,
            f"[reject_request] rola 'Worker' bez uprawnień powinna być przekierowana "
            f"na dashboard, otrzymano redirect na {response.url}",
        )
        self.assertEqual(
            AuthLog.objects.filter(action='access_denied_403').count(), logs_before + 1,
        )
        self.client.logout()

        for role in ["Admin", "Manager", "HR"]:
            self.login_as(role)
            response = self.client.post(url)
            if response.status_code == 302:
                self.assertNotEqual(
                    response.url, dashboard_url,
                    f"[reject_request] rola '{role}' z uprawnieniami nie powinna być "
                    f"przekierowana na dashboard",
                )
            self.client.logout()

    # --- can_change_request --- (True: Admin, Worker / False: Manager, HR)
    def test_leave_request_update_permissions(self):
        # Test edycji wniosku urlopowego – dozwolone tylko dla Admina oraz
        # właściciela wniosku (Worker). Manager/HR -> redirect na dashboard.
        pending = LeaveRequest.objects.create(
            employee=self.users["Worker"],
            start_date="2026-09-15",
            end_date="2026-09-16",
            amount_days=2,
            status=LeaveRequest.Status.PENDING,
        )
        url = reverse("leave_request_edit", kwargs={"pk": pending.pk})
        dashboard_url = reverse('dashboard')

        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        for role in ["Manager", "HR"]:
            self.login_as(role)
            logs_before = AuthLog.objects.filter(action='access_denied_403').count()
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 302,
                f"[leave_request_edit] rola '{role}' bez uprawnień powinna dostać redirect, "
                f"otrzymano {response.status_code}",
            )
            self.assertEqual(
                response.url, dashboard_url,
                f"[leave_request_edit] rola '{role}' bez uprawnień powinna być "
                f"przekierowana na dashboard, otrzymano redirect na {response.url}",
            )
            self.assertEqual(
                AuthLog.objects.filter(action='access_denied_403').count(), logs_before + 1,
            )
            self.client.logout()

        self.login_as("Admin")
        response = self.client.get(url)
        if response.status_code == 302:
            self.assertNotEqual(response.url, dashboard_url)
        self.client.logout()

        self.login_as("Worker")
        response = self.client.get(url)
        if response.status_code == 302:
            self.assertNotEqual(response.url, dashboard_url)
        self.client.logout()


class CancelLeaveViewPermissionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Przygotowanie dedykowanych użytkowników i profili dla testów anulowania urlopu
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
        # Metoda pomocnicza logująca użytkownika w kontekście anulowania wniosków
        self.client.login(username=f"cancel_{role.lower()}", password="testpass123")

    def make_request(self, owner):
        # Metoda pomocnicza tworząca wniosek powiązany z konkretnym właścicielem
        return LeaveRequest.objects.create(
            employee=owner,
            start_date="2026-08-01",
            end_date="2026-08-05",
            amount_days=5,
            status=LeaveRequest.Status.PENDING,
        )

    def test_anonymous_cannot_cancel(self):
        # Sprawdzenie, czy niezalogowany użytkownik zostanie przekierowany przy próbie anulowania urlopu
        leave_request = self.make_request(self.users["Worker"])
        url = reverse("leave_request_cancel", kwargs={"pk": leave_request.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    def test_roles_with_permission_are_not_forbidden(self):
        # Sprawdzenie, czy role posiadające uprawnienie (Worker) mogą
        # pomyślnie anulować wniosek (brak redirectu na dashboard)
        dashboard_url = reverse('dashboard')
        for role in ["Worker"]:
            self.login_as(role)
            leave_request = self.make_request(self.users[role])
            url = reverse("leave_request_cancel", kwargs={"pk": leave_request.pk})
            response = self.client.post(url)
            if response.status_code == 302:
                self.assertNotEqual(
                    response.url, dashboard_url,
                    f"Rola '{role}' ma can_cancel_request=True, nie powinna być "
                    f"przekierowana na dashboard",
                )
            self.client.logout()

    def test_roles_without_permission_get_redirected_to_dashboard(self):
        # Sprawdzenie, czy role bez uprawnień (Manager, HR) dostaną redirect
        # na dashboard przy próbie anulowania, wraz z wpisem w AuthLog
        dashboard_url = reverse('dashboard')
        for role in ["Manager", "HR"]:
            self.login_as(role)
            leave_request = self.make_request(self.users[role])
            url = reverse("leave_request_cancel", kwargs={"pk": leave_request.pk})

            logs_before = AuthLog.objects.filter(action='access_denied_403').count()
            response = self.client.post(url)

            self.assertEqual(
                response.status_code, 302,
                f"Rola '{role}' ma can_cancel_request=False, powinna dostać redirect, "
                f"otrzymano {response.status_code}",
            )
            self.assertEqual(
                response.url, dashboard_url,
                f"Rola '{role}' bez uprawnień powinna być przekierowana na dashboard, "
                f"otrzymano redirect na {response.url}",
            )
            self.assertEqual(
                AuthLog.objects.filter(action='access_denied_403').count(), logs_before + 1,
            )
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