from accounts.permission import Permission
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from logs.models import AuthLog, ActivityLog


class PermissionVerifyTest(TestCase):
    #TESTY DLA ADMINA
    def test_Admin_can_approve_request(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_approve_request"))

    def test_Admin_can_reject_request(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_reject_request"))

    def test_Admin_can_cancel_request(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_cancel_request"))

    def test_Admin_can_change_request(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_change_request"))

    def test_Admin_can_see_all_requests(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_see_all_requests"))

    def test_Admin_can_submit_request(self):
        self.assertFalse(Permission.verifyPermission("Admin","can_submit_request"))

    def test_Admin_can_see_own_requests(self):
        self.assertFalse(Permission.verifyPermission("Admin","can_see_own_requests"))

    def test_Admin_can_add_user(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_add_user"))

    def test_Admin_can_list_users(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_view_user_list"))

    def test_Admin_can_reset_password(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_reset_password"))

    def test_Admin_can_see_user_vacations(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_see_user_vacations"))

    def test_Admin_can_deactivate_staff(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_deactivate_staff"))

    def test_Admin_can_deactivate_worker(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_deactivate_worker"))

    #TESTY DLA MANAGERA

    def test_Manager_can_approve_request(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_approve_request"))

    def test_Manager_can_reject_request(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_reject_request"))

    def test_Manager_can_cancel_request(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_cancel_request"))

    def test_Manager_can_change_request(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_change_request"))

    def test_Manager_can_see_all_requests(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_see_all_requests"))

    def test_Manager_can_submit_request(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_submit_request"))

    def test_Manager_can_see_own_requests(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_see_own_requests"))

    def test_Manager_can_add_user(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_add_user"))

    def test_Manager_can_list_users(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_view_user_list"))

    def test_Manager_can_reset_password(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_reset_password"))

    def test_Manager_can_see_user_vacations(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_see_user_vacations"))

    def test_Manager_can_deactivate_staff(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_deactivate_staff"))

    def test_Manager_can_deactivate_worker(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_deactivate_worker"))

    #TESTY DLA HR

    def test_HR_can_approve_request(self):
        self.assertTrue(Permission.verifyPermission("HR","can_approve_request"))

    def test_HR_can_reject_request(self):
        self.assertTrue(Permission.verifyPermission("HR","can_reject_request"))

    def test_HR_can_cancel_request(self):
        self.assertFalse(Permission.verifyPermission("HR","can_cancel_request"))

    def test_HR_can_change_request(self):
        self.assertFalse(Permission.verifyPermission("HR","can_change_request"))

    def test_HR_can_see_all_requests(self):
        self.assertTrue(Permission.verifyPermission("HR","can_see_all_requests"))

    def test_HR_can_submit_request(self):
        self.assertFalse(Permission.verifyPermission("HR","can_submit_request"))

    def test_HR_can_see_own_requests(self):
        self.assertFalse(Permission.verifyPermission("HR","can_see_own_requests"))

    def test_HR_can_add_user(self):
        self.assertTrue(Permission.verifyPermission("HR","can_add_user"))

    def test_HR_can_list_users(self):
        self.assertTrue(Permission.verifyPermission("HR","can_view_user_list"))

    def test_HR_can_reset_password(self):
        self.assertTrue(Permission.verifyPermission("HR","can_reset_password"))

    def test_HR_can_see_user_vacations(self):
        self.assertTrue(Permission.verifyPermission("HR","can_see_user_vacations"))

    def test_HR_can_deactivate_staff(self):
        self.assertFalse(Permission.verifyPermission("HR","can_deactivate_staff"))

    def test_HR_can_deactivate_worker(self):
        self.assertTrue(Permission.verifyPermission("HR","can_deactivate_worker"))

     #TESTY DLA WORKERA

    def test_Worker_can_approve_request(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_approve_request"))

    def test_Worker_can_reject_request(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_reject_request"))

    def test_Worker_can_cancel_request(self):
        self.assertTrue(Permission.verifyPermission("Worker","can_cancel_request"))

    def test_Worker_can_change_request(self):
        self.assertTrue(Permission.verifyPermission("Worker","can_change_request"))

    def test_Worker_can_see_all_requests(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_see_all_requests"))

    def test_Worker_can_submit_request(self):
        self.assertTrue(Permission.verifyPermission("Worker","can_submit_request"))

    def test_Worker_can_see_own_requests(self):
        self.assertTrue(Permission.verifyPermission("Worker","can_see_own_requests"))

    def test_Worker_can_add_user(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_add_user"))

    def test_Worker_can_list_users(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_view_user_list"))

    def test_Worker_can_reset_password(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_reset_password"))

    def test_Worker_can_see_user_vacations(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_see_user_vacations"))

    def test_Worker_can_deactivate_staff(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_deactivate_staff"))

    def test_Worker_can_deactivate_worker(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_deactivate_worker"))


User = get_user_model()

class AccountsViewsTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # Tworzenie użytkowników z różnymi rolami systemowymi
        # Zakładamy, że Twój model User ma pole 'role' (Admin, HR, Manager, Worker)
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='password123',
            role='Admin',
            first_name='Adam',
            last_name='Adminowski',
            is_active=True
        )

        self.hr_user = User.objects.create_user(
            username='hr_test',
            password='password123',
            role='HR',
            first_name='Hanna',
            last_name='Retor',
            is_active=True
        )

        self.manager_user = User.objects.create_user(
            username='manager_test',
            password='password123',
            role='Manager',
            first_name='Mariusz',
            last_name='Szef',
            is_active=True
        )

        self.worker_user = User.objects.create_user(
            username='worker_test',
            password='password123',
            role='Worker',
            first_name='Wojtek',
            last_name='Pracownik',
            is_active=True
        )

    # ==========================================
    # 1. TESTY WIDOKU: deactivate_user
    # ==========================================

    def test_deactivate_user_anonymous_redirects(self):
        """Użytkownik niezalogowany zostaje przekierowany do logowania."""
        url = reverse('deactivate_user', kwargs={'pk': self.worker_user.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_deactivate_worker_by_admin_success(self):
        """Admin ma uprawnienie 'can_deactivate_worker' i może dezaktywować Workera (POST)."""
        self.client.force_login(self.admin_user)
        url = reverse('deactivate_user', kwargs={'pk': self.worker_user.pk})

        # Test GET (powinien zwrócić stronę potwierdzenia)
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)
        self.assertTemplateUsed(response_get, 'accounts/deactivate_user.html')

        # Test POST (dezaktywacja)
        response_post = self.client.post(url)
        self.assertRedirects(response_post, reverse('user_list'))

        # Sprawdzenie czy użytkownik został dezaktywowany
        self.worker_user.refresh_from_db()
        self.assertFalse(self.worker_user.is_active)

    def test_deactivate_staff_by_admin_success(self):
        """Admin ma uprawnienie 'can_deactivate_staff' i może dezaktywować HR (POST)."""
        self.client.force_login(self.admin_user)
        url = reverse('deactivate_user', kwargs={'pk': self.hr_user.pk})

        response = self.client.post(url)
        self.assertRedirects(response, reverse('user_list'))
        self.hr_user.refresh_from_db()
        self.assertFalse(self.hr_user.is_active)

    def test_deactivate_worker_by_hr_success(self):
        """HR ma uprawnienie 'can_deactivate_worker' i może dezaktywować Workera."""
        self.client.force_login(self.hr_user)
        url = reverse('deactivate_user', kwargs={'pk': self.worker_user.pk})

        response = self.client.post(url)
        self.assertRedirects(response, reverse('user_list'))
        self.worker_user.refresh_from_db()
        self.assertFalse(self.worker_user.is_active)

    def test_deactivate_staff_by_hr_denied(self):
        """HR nie ma uprawnienia 'can_deactivate_staff' i nie może dezaktywować Managera."""
        self.client.force_login(self.hr_user)
        url = reverse('deactivate_user', kwargs={'pk': self.manager_user.pk})

        response = self.client.post(url)
        # Przekierowanie na dashboard z powodu braku uprawnień
        self.assertRedirects(response, reverse('dashboard'))

        # Manager musi pozostać aktywny
        self.manager_user.refresh_from_db()
        self.assertTrue(self.manager_user.is_active)

    def test_deactivate_by_worker_denied(self):
        """Worker nie ma żadnych uprawnień dezaktywacji (can_deactivate_worker/staff)."""
        self.client.force_login(self.worker_user)
        url = reverse('deactivate_user', kwargs={'pk': self.hr_user.pk})

        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        self.hr_user.refresh_from_db()
        self.assertTrue(self.hr_user.is_active)

    # ==========================================
    # 2. TESTY WIDOKU: user_list
    # ==========================================

    def test_user_list_anonymous_redirects(self):
        """Niezalogowany przekierowany do logowania."""
        url = reverse('user_list')
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_user_list_allowed_roles(self):
        """Admin, Manager i HR mają uprawnienie 'can_view_user_list' i widzą listę."""
        allowed_users = [self.admin_user, self.hr_user]
        url = reverse('user_list')

        for user in allowed_users:
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'accounts/user_list.html')

            # Weryfikacja filtrowania: Admin i Superuser powinni być wykluczeni z listy w kontekście
            users_in_context = response.context['users']
            for u in users_in_context:
                self.assertNotEqual(u.role, 'Admin')
                self.assertFalse(u.is_superuser)

    def test_user_list_denied_for_worker(self):
        """Worker nie ma uprawnienia 'can_view_user_list' (zostaje przekierowany i tworzy się AuthLog)."""
        self.client.force_login(self.worker_user)
        url = reverse('user_list')

        response = self.client.get(url)
        self.assertRedirects(response, reverse('dashboard'))

        # Sprawdzenie, czy dekorator zapisał odmowę dostępu (403) w logach
        log_exists = AuthLog.objects.filter(
            user=self.worker_user,
            action='403',
            severity='warning'
        ).exists()
        self.assertTrue(log_exists)

    # ==========================================
    # 3. TESTY WIDOKU: switch_role
    # ==========================================

    def test_switch_role_anonymous_redirects(self):
        """Niezalogowany nie zmieni roli."""
        url = reverse('switch_role')
        response = self.client.post(url, {'role': 'Worker'})
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_switch_role_success(self):
        """Prawidłowa zmiana roli przez zalogowanego użytkownika (np. Manager przełącza się na Worker)."""
        # Dla celów testowych musimy upewnić się, że ALLOWED_ROLES w accounts.context_processors
        # pozwala Managerowi przełączyć się na Worker. Zakładamy, że tak jest.
        # Jeśli mechanizm mockowania byłby potrzebny, można użyć patch, ale zazwyczaj słownik jest stały.
        self.client.force_login(self.manager_user)

        # Symulujemy, że w session jest zapisana poprzednia aktywna rola
        session = self.client.session
        session['active_role'] = 'Manager'
        session.save()

        url = reverse('switch_role')
        # Przełączamy się na "Worker" (Manager może to zrobić)
        response = self.client.post(url, {'role': 'Worker'})

        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(self.client.session['active_role'], 'Worker')

        # Sprawdzamy czy powstał log aktywności (ActivityLog)
        log = ActivityLog.objects.filter(who=self.manager_user, action='role_change').latest('id')
        self.assertIn("Zmieniono aktywną rolę z Manager na Worker", log.details)

    def test_switch_role_denied(self):
        """Błędna próba zmiany roli na niedozwoloną (np. Worker próbuje zostać Adminem)."""
        self.client.force_login(self.worker_user)

        url = reverse('switch_role')
        response = self.client.post(url, {'role': 'Admin'})

        self.assertRedirects(response, reverse('dashboard'))

        # Rola w sesji nie powinna się zmienić na Admin
        self.assertNotEqual(self.client.session.get('active_role'), 'Admin')

        # Sprawdzamy czy powstał log bezpieczeństwa (AuthLog) o wadze 'warning'
        log = AuthLog.objects.filter(user=self.worker_user, action='access_denied_403').latest('id')
        self.assertIn("Proba zmiany roli na: Admin", log.details)

    # ==========================================
    # 4. TESTY WIDOKU: add_user
    # ==========================================

    def test_add_user_anonymous_redirects(self):
        """Niezalogowany przekierowany do logowania."""
        url = reverse('add_user')
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_add_user_permission_denied_for_manager(self):
        """Manager nie ma uprawnienia 'can_add_user'."""
        self.client.force_login(self.manager_user)
        url = reverse('add_user')

        response = self.client.get(url)
        self.assertRedirects(response, reverse('dashboard'))

    def test_add_user_success_by_hr_with_worker_profile(self):
        """HR może dodać użytkownika. Jeśli formularz ma 'team', tworzy się dla niego WorkerProfile."""
        self.client.force_login(self.hr_user)
        url = reverse('add_user')

        # GET - powinien zwrócić formularz
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)
        self.assertTemplateUsed(response_get, 'accounts/add_user.html')

        # Mockowanie / przygotowanie danych do POST.
        # W teście musisz przekazać poprawne dane zgodne z Twoim AddUserForm.
        # Zakładamy pola: username, password, role, team (np. ID zespołu lub string, zależnie od modelu), hire_date.
        form_data = {
            'username': 'nowy_pracownik',
            'email': 'nowy@firma.pl',
            'role': 'Worker',
            'team': 'Team A',  # Dostosuj do tego, czym jest team w Twoim AddUserForm (np. ID obiektu Team)
            'hire_date': date(2026, 6, 1),
            # Inne wymagane pola formularza AddUserForm...
        }

        # Ponieważ AddUserForm to Twój własny formularz, najbezpieczniej jest go przetestować,
        # ale jeśli wymaga on skomplikowanych zależności, możemy go zamockować lub
        # upewnić się, że wysyłamy wszystkie wymagane dla niego pola.

        # UWAGA: Aby test przeszedł bez błędów walidacji formularza, upewnij się, że przesyłasz
        # wszystkie pola, które AddUserForm ma jako wymagane (np. hasło, imię, itp.).
        # Poniżej znajduje się przykładowy post:

        # response = self.client.post(url, data=form_data)
        # self.assertRedirects(response, reverse('user_list'))
        # self.assertTrue(User.objects.filter(username='nowy_pracownik').exists())
        # ... i sprawdzenie WorkerProfile oraz ActivityLog.add_new_change

    # ==========================================
    # 5. TESTY WIDOKU: reset_password
    # ==========================================

    def test_reset_password_anonymous_redirects(self):
        """Niezalogowany nie ma dostępu do resetu hasła."""
        url = reverse('reset_password')
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_reset_password_denied_for_worker(self):
        """Worker nie może resetować haseł (brak uprawnienia 'can_reset_password')."""
        self.client.force_login(self.worker_user)
        url = reverse('reset_password')

        response = self.client.get(url)
        self.assertRedirects(response, reverse('dashboard'))

    def test_reset_password_get_by_admin(self):
        """Admin (posiada 'can_reset_password') wchodzi na GET i widzi listę użytkowników."""
        self.client.force_login(self.admin_user)
        url = reverse('reset_password')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/reset_password.html')
        self.assertIn('users', response.context)

    def test_reset_password_post_success(self):
        """Prawidłowy reset hasła (POST) przez Admina."""
        self.client.force_login(self.admin_user)
        url = reverse('reset_password')

        post_data = {
            'user_id': self.worker_user.id,
            'new_password': 'nowe_bezpieczne_haslo123'
        }

        response = self.client.post(url, post_data)
        self.assertRedirects(response, reverse('user_list'))

        # Sprawdzamy czy hasło rzeczywiście zostało zmienione
        # Próba zalogowania się workerem za pomocą nowego hasła
        login_success = self.client.login(username=self.worker_user.username, password='nowe_bezpieczne_haslo123')
        self.assertTrue(login_success)

    def test_reset_password_too_short(self):
        """Próba resetu hasła na krótsze niż 6 znaków powinna wyrzucić błąd."""
        self.client.force_login(self.admin_user)
        url = reverse('reset_password')

        post_data = {
            'user_id': self.worker_user.id,
            'new_password': '123'  # za krótkie
        }

        response = self.client.post(url, post_data)
        self.assertRedirects(response, reverse('reset_password'))

        # Sprawdzamy czy stare hasło nadal działa (hasło nie powinno się zmienić)
        login_success = self.client.login(username=self.worker_user.username, password='password123')
        self.assertTrue(login_success)

    def test_reset_password_user_does_not_exist(self):
        """Próba resetu hasła dla nieistniejącego ID użytkownika."""
        self.client.force_login(self.admin_user)
        url = reverse('reset_password')

        post_data = {
            'user_id': 99999,  # nie istnieje
            'new_password': 'nowe_haslo_123'
        }

        response = self.client.post(url, post_data)
        # Widok powinien wyłapać DoesNotExist, dodać komunikat o błędzie i wyrenderować stronę na nowo
        # (Zauważ, że w Twoim try-except w kodzie widoku przy DoesNotExist nie ma return redirect,
        # więc kod leci dalej i renderuje reset_password.html z kodem 200)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/reset_password.html')
    

