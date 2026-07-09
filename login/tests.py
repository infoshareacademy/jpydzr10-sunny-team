from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from django.utils import timezone
from datetime import timedelta
from logs.models import LoginAttempt
from login.views import MAX_FAILED_ATTEMPTS, LOCKOUT_WINDOW_MINUTES


class LoginViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')

        # konto aktywne
        self.active_user = User.objects.create_user(
            username='Jan_A',
            password='haslo123',
            is_active=True,
        )

        # konto zablokowane
        self.inactive_user = User.objects.create_user(
            username='Stefan_Z',
            password='innehaslo123',
            is_active=False,
        )

    # TEST 1: GET --> 200
    # czy strona logowania się otwiera?
    def test_get_login_page_returns_200(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    # TEST 2: Błędne dane --> zostajemy na stronie logowania
    def test_post_wrong_credentials_stays_on_login(self):
        response = self.client.post(self.login_url, {
            'username': 'Jan_A',
            'password': 'ZLE_HASLO',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    # TEST 3: Poprawne dane --> przekierowanie (kod 302)
    def test_post_correct_credentials_redirects(self):
        response = self.client.post(self.login_url, {
            'username': 'Jan_A',
            'password': 'haslo123',
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    # TEST 4: Konto nieaktywne --> odmowa logowania (bez względu na dobre/złe hasło)
    def test_post_inactive_user_cannot_login(self):
        response = self.client.post(self.login_url, {
            'username': 'Stefan_Z',
            'password': 'innehaslo123',  # hasło poprawne, ale konto nieaktywne
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    # TEST 5: Hasło krótsze niż 6 znaków --> odmowa
    def test_post_password_too_short_cannot_login(self):
        response = self.client.post(self.login_url, {
            'username': 'Jan_A',
            'password': 'abc',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class LoginAttemptModelTests(TestCase):
    """Testy modelu LoginAttempt."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='jan_kowalski',
            password='TajneHaslo123!',
        )

    def test_create_successful_attempt(self):
        attempt = LoginAttempt.objects.create(
            user=self.user,
            username='jan_kowalski',
            ip_address='127.0.0.1',
            success=True,
        )
        self.assertTrue(attempt.success)
        self.assertEqual(attempt.user, self.user)
        self.assertIsNotNone(attempt.timestamp)

    def test_create_failed_attempt_without_user(self):
        # Nieudana proba - user moze byc None (np. zly login)
        attempt = LoginAttempt.objects.create(
            user=None,
            username='nieistniejacy_user',
            ip_address='10.0.0.5',
            success=False,
        )
        self.assertIsNone(attempt.user)
        self.assertFalse(attempt.success)
        self.assertEqual(attempt.username, 'nieistniejacy_user')

    def test_success_defaults_to_false(self):
        attempt = LoginAttempt.objects.create(
            user=None,
            username='ktos',
            ip_address='127.0.0.1',
        )
        self.assertFalse(attempt.success)

    def test_invalidated_defaults_to_false(self):
        attempt = LoginAttempt.objects.create(
            user=None,
            username='ktos',
            ip_address='127.0.0.1',
            success=False,
        )
        self.assertFalse(attempt.invalidated)

    def test_timestamp_auto_now_add(self):
        before = timezone.now()
        attempt = LoginAttempt.objects.create(
            user=self.user,
            username='jan_kowalski',
            ip_address='127.0.0.1',
            success=True,
        )
        after = timezone.now()
        self.assertTrue(before <= attempt.timestamp <= after)

    def test_str_representation(self):
        attempt = LoginAttempt.objects.create(
            user=self.user,
            username='jan_kowalski',
            ip_address='127.0.0.1',
            success=True,
        )
        text = str(attempt)
        self.assertIn('jan_kowalski', text)
        self.assertIn('OK', text)

    def test_str_representation_failed(self):
        attempt = LoginAttempt.objects.create(
            user=None,
            username='jan_kowalski',
            ip_address='127.0.0.1',
            success=False,
        )
        self.assertIn('FAIL', str(attempt))

    def test_deleting_user_sets_null(self):
        # on_delete=SET_NULL - usuniecie usera nie kasuje logu
        attempt = LoginAttempt.objects.create(
            user=self.user,
            username='jan_kowalski',
            ip_address='127.0.0.1',
            success=True,
        )
        self.user.delete()
        attempt.refresh_from_db()
        self.assertIsNone(attempt.user)
        # username zostaje jako tekst, niezalezny od FK
        self.assertEqual(attempt.username, 'jan_kowalski')

    def test_ip_address_nullable(self):
        attempt = LoginAttempt.objects.create(
            user=self.user,
            username='jan_kowalski',
            ip_address=None,
            success=True,
        )
        self.assertIsNone(attempt.ip_address)

    def test_ordering_most_recent_first(self):
        old = LoginAttempt.objects.create(
            user=self.user, username='jan_kowalski',
            ip_address='127.0.0.1', success=True,
        )
        old.timestamp = timezone.now() - timedelta(hours=1)
        old.save(update_fields=['timestamp'])

        new = LoginAttempt.objects.create(
            user=self.user, username='jan_kowalski',
            ip_address='127.0.0.1', success=True,
        )

        attempts = list(LoginAttempt.objects.all())
        self.assertEqual(attempts[0].pk, new.pk)
        self.assertEqual(attempts[1].pk, old.pk)


class LoginLockoutTests(TestCase):
    """Testy mechanizmu lockout po N nieudanych probach."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(
            username='jan_kowalski',
            password='TajneHaslo123!',
            is_active=True,
        )

    def _fail_login(self, username='jan_kowalski', password='zle_haslo'):
        return self.client.post(self.login_url, {
            'username': username,
            'password': password,
        })

    def test_successful_login_creates_success_attempt(self):
        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        attempt = LoginAttempt.objects.filter(username='jan_kowalski').latest('timestamp')
        self.assertTrue(attempt.success)
        self.assertEqual(attempt.user, self.user)

    def test_failed_login_creates_failed_attempt(self):
        self._fail_login()
        attempt = LoginAttempt.objects.filter(username='jan_kowalski').latest('timestamp')
        self.assertFalse(attempt.success)

    def test_login_allowed_below_threshold(self):
        # N-1 nieudanych prob - konto jeszcze NIE zablokowane
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            self._fail_login()

        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',  # poprawne haslo
        })
        # Powinno zalogowac (redirect na dashboard), bo limit nie zostal osiagniety
        self.assertRedirects(response, reverse('dashboard'))

    def test_lockout_triggers_after_n_failed_attempts(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login()

        # Kolejna proba - nawet z poprawnym haslem - powinna zostac zablokowana
        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.assertEqual(response.status_code, 200)  # nie redirect
        self.assertContains(response, 'Too many failed login attempts')

    def test_locked_out_user_not_authenticated(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login()

        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_lockout_is_per_username_and_ip(self):
        # N nieudanych prob dla jan_kowalski
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login(username='jan_kowalski')

        # Inny user z tego samego IP - nie powinien byc zablokowany
        User.objects.create_user(username='anna_nowak', password='InneHaslo456!', is_active=True)
        response = self.client.post(self.login_url, {
            'username': 'anna_nowak',
            'password': 'InneHaslo456!',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_old_failed_attempts_outside_window_do_not_count(self):
        # Symulujemy N nieudanych prob, ale sprzed okna czasowego
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login()

        old_time = timezone.now() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES + 1)
        LoginAttempt.objects.filter(username='jan_kowalski').update(timestamp=old_time)

        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_inactive_user_counts_as_failed_attempt(self):
        self.user.is_active = False
        self.user.save()

        for _ in range(MAX_FAILED_ATTEMPTS):
            response = self.client.post(self.login_url, {
                'username': 'jan_kowalski',
                'password': 'TajneHaslo123!',  # poprawne haslo, ale konto nieaktywne
            })
            # authenticate() zwraca None dla is_active=False,
            # wiec trafiamy w galaz "user is None" -> nadpisany komunikat 'Invalid credentials.'
            self.assertContains(response, 'Invalid credentials.')

        failed_count = LoginAttempt.objects.filter(
            username='jan_kowalski', success=False
        ).count()
        self.assertEqual(failed_count, MAX_FAILED_ATTEMPTS)

    def test_invalid_form_counts_as_failed_attempt(self):
        # Pusty username/password - form.is_valid() == False
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.client.post(self.login_url, {'username': '', 'password': ''})

        count = LoginAttempt.objects.filter(username='').count()
        self.assertEqual(count, MAX_FAILED_ATTEMPTS)

    def test_successful_login_invalidates_previous_failed_attempts(self):
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            self._fail_login()

        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.assertRedirects(response, reverse('dashboard'))

        # Historia  istnieje w bazie
        all_failed = LoginAttempt.objects.filter(username='jan_kowalski', success=False)
        self.assertEqual(all_failed.count(), MAX_FAILED_ATTEMPTS - 1)

        # ale wszystkie oznaczone jako invalidated
        self.assertTrue(all(a.invalidated for a in all_failed))

        self.client.get(reverse('logout'))

        # Kolejna nieudana proba nie powinna od razu wywolac lockout
        response2 = self._fail_login()
        self.assertContains(response2, 'Invalid credentials.')
        self.assertNotContains(response2, 'Too many failed login attempts')

    def test_invalidated_attempts_are_not_deleted(self):
        self._fail_login()
        self._fail_login()

        count_before = LoginAttempt.objects.count()

        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })

        count_after = LoginAttempt.objects.count()
        # Rekordy nadal istnieja
        self.assertEqual(count_after, count_before + 1)

    def test_invalidated_true_after_successful_login(self):
        self._fail_login()
        attempt = LoginAttempt.objects.filter(username='jan_kowalski', success=False).first()
        self.assertFalse(attempt.invalidated)

        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })

        attempt.refresh_from_db()
        self.assertTrue(attempt.invalidated)

    def test_reset_does_not_affect_other_users_failed_attempts(self):
        User.objects.create_user(username='anna_nowak', password='InneHaslo456!', is_active=True)

        # Nieudane proby dla anna_nowak
        self.client.post(self.login_url, {'username': 'anna_nowak', 'password': 'zle'})
        self.client.post(self.login_url, {'username': 'anna_nowak', 'password': 'zle'})

        # Udane logowanie jan_kowalski
        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })

        # Nieudane proby anny powinny nadal byc w bazie
        anna_failed_count = LoginAttempt.objects.filter(
            username='anna_nowak', success=False
        ).count()
        self.assertEqual(anna_failed_count, 2)