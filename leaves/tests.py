from accounts.models import User
from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from leaves.models import LeaveRequest, WorkerProfile

User = get_user_model()


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
  - rola BEZ danego uprawnienia -> 403 (PermissionDenied)
  - rola Z danym uprawnieniem   -> NIE 403
  - użytkownik niezalogowany    -> 302 (redirect do loginu), nigdy 403/500
"""

class ViewsPermissionMatrixTestCase(TestCase):
    """
    Dla widoków opartych o GET sprawdza pełną macierz: role z uprawnieniem
    -> NIE 403, role bez uprawnienia -> 403, niezalogowany -> 302.
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
        # Uniwersalna metoda sprawdzająca dostęp (302 dla gościa, 403 dla zablokowanych, brak 403 dla dozwolonych)
        url = reverse(url_name, kwargs=url_kwargs or {})

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
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 403,
                f"[{url_name}] rola '{role}' bez uprawnień powinna dostać 403, "
                f"otrzymano {response.status_code}",
            )
            self.client.logout()

        for role in allowed_roles:
            self.login_as(role)
            response = self.client.get(url)
            self.assertNotEqual(
                response.status_code, 403,
                f"[{url_name}] rola '{role}' z uprawnieniami nie powinna dostać 403",
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

    # --- can_add_user --- (True: Admin, HR / False: Manager, Worker)
    def test_add_user_permissions(self):
        # Test uprawnień do widoku dodawania nowego użytkownika (Admin i HR)
        self.assert_forbidden_for_roles(
            "add_user",
            forbidden_roles=["Manager", "Worker"],
            allowed_roles=["Admin", "HR"],
        )

    # --- can_reset_password --- (True: Admin, HR / False: Manager, Worker)
    def test_reset_password_permissions(self):
        # Test uprawnień do widoku resetowania haseł (Admin i HR)
        self.assert_forbidden_for_roles(
            "reset_password",
            forbidden_roles=["Manager", "Worker"],
            allowed_roles=["Admin", "HR"],
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

    # --- can_view_logs --- (True: Admin, Manager, HR / False: Worker)
    def test_log_history_permissions(self):
        # Test dostępu do historii logów systemowych (Admin, HR, Manager)
        self.assert_forbidden_for_roles(
            "log_history",
            forbidden_roles=["Worker"],
            allowed_roles=["Admin", "HR", "Manager"],
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
        # Test akceptacji wniosku (POST) – Worker dostaje 403, kadra zarządzająca przechodzi pomyśln Trump
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
        self.assertEqual(
            response.status_code, 403,
            f"[approve_request] rola 'Worker' bez uprawnień powinna dostać 403, "
            f"otrzymano {response.status_code}",
        )
        self.client.logout()

        for role in ["Admin", "Manager", "HR"]:
            self.login_as(role)
            response = self.client.post(url)
            self.assertNotEqual(
                response.status_code, 403,
                f"[approve_request] rola '{role}' z uprawnieniami nie powinna dostać 403",
            )
            self.client.logout()

    # --- can_reject_request --- (True: Admin, Manager, HR / False: Worker)
    def test_reject_request_permissions(self):
        # Test odrzucenia wniosku (POST) – Worker dostaje 403, Admin/Manager/HR mają dostęp
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
        self.assertEqual(
            response.status_code, 403,
            f"[reject_request] rola 'Worker' bez uprawnień powinna dostać 403, "
            f"otrzymano {response.status_code}",
        )
        self.client.logout()

        for role in ["Admin", "Manager", "HR"]:
            self.login_as(role)
            response = self.client.post(url)
            self.assertNotEqual(
                response.status_code, 403,
                f"[reject_request] rola '{role}' z uprawnieniami nie powinna dostać 403",
            )
            self.client.logout()

    # --- can_change_request --- (True: Admin, Worker / False: Manager, HR)
    def test_leave_request_update_permissions(self):
        # Test edycji wniosku urlopowego – dozwolone tylko dla Admina oraz właściciela wniosku (Worker)
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
            self.assertEqual(
                response.status_code, 403,
                f"[leave_request_edit] rola '{role}' bez uprawnień powinna dostać 403, "
                f"otrzymano {response.status_code}",
            )
            self.client.logout()

        self.login_as("Admin")
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 403)
        self.client.logout()

        self.login_as("Worker")
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 403)
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
        # Sprawdzenie, czy role posiadające uprawnienie (Admin, Worker) mogą pomyślnie anulować wniosek (brak 403)
        for role in ["Admin", "Worker"]:
            self.login_as(role)
            leave_request = self.make_request(self.users[role])
            url = reverse("leave_request_cancel", kwargs={"pk": leave_request.pk})
            response = self.client.post(url)
            self.assertNotEqual(
                response.status_code, 403,
                f"Rola '{role}' ma can_cancel_request=True, nie powinna dostać 403",
            )
            self.client.logout()

    def test_roles_without_permission_get_403(self):
        # Sprawdzenie, czy role bez uprawnień (Manager, HR) dostaną 403 (Forbidden) przy próbie anulowania
        for role in ["Manager", "HR"]:
            self.login_as(role)
            leave_request = self.make_request(self.users[role])
            url = reverse("leave_request_cancel", kwargs={"pk": leave_request.pk})
            response = self.client.post(url)
            self.assertEqual(
                response.status_code, 403,
                f"Rola '{role}' ma can_cancel_request=False, powinna dostać 403, "
                f"otrzymano {response.status_code}",
            )
            self.client.logout()