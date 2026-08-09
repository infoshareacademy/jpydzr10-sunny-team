from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from django.utils import timezone
from datetime import timedelta
from logs.models import AuthLog
from logs.utils import MAX_FAILED_ATTEMPTS, LOCKOUT_WINDOW_MINUTES

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

        # konto zablokowane (nieaktywne)
        self.inactive_user = User.objects.create_user(
            username='Stefan_Z',
            password='innehaslo123',
            is_active=False,
        )

    # TEST 1: GET --> 200
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
        self.assertContains(response, 'Błędne dane.')

    # TEST 3: Poprawne dane --> przekierowanie (kod 302)
    def test_post_correct_credentials_redirects(self):
        response = self.client.post(self.login_url, {
            'username': 'Jan_A',
            'password': 'haslo123',
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    # TEST 4: Konto nieaktywne --> odmowa logowania
    # authenticate() zwraca None dla is_active=False, form.is_valid() == False,
    # więc trafiamy w gałąź "invalid form" i widzimy nadpisany komunikat 'Błędne dane.'
    def test_post_inactive_user_cannot_login(self):
        response = self.client.post(self.login_url, {
            'username': 'Stefan_Z',
            'password': 'innehaslo123',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, 'Błędne dane.')

        attempt = AuthLog.objects.filter(action='login_failed').latest('timestamp')
        self.assertEqual(attempt.user, self.inactive_user)

    # TEST 5: Hasło krótsze niż 6 znaków --> odmowa
    def test_post_password_too_short_cannot_login(self):
        response = self.client.post(self.login_url, {
            'username': 'Jan_A',
            'password': 'abc',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class AuthLogModelTests(TestCase):
    """Testy modelu AuthLog."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='jan_kowalski',
            password='TajneHaslo123!',
        )

    def test_create_successful_attempt(self):
        attempt = AuthLog.objects.create(
            user=self.user,
            username=None,
            ip_address='127.0.0.1',
            action='login_success',
            severity='info',
        )
        self.assertEqual(attempt.action, 'login_success')
        self.assertEqual(attempt.user, self.user)
        self.assertIsNotNone(attempt.timestamp)

    def test_create_failed_attempt_without_user(self):
        # Nieudana proba - user moze byc None (np. zly login, nieistniejacy uzytkownik)
        attempt = AuthLog.objects.create(
            user=None,
            username='nieistniejacy_user',
            ip_address='10.0.0.5',
            action='login_failed',
            severity='warning',
        )
        self.assertIsNone(attempt.user)
        self.assertEqual(attempt.action, 'login_failed')
        self.assertEqual(attempt.username, 'nieistniejacy_user')

    def test_severity_defaults_to_info(self):
        attempt = AuthLog.objects.create(
            user=None,
            username='ktos',
            ip_address='127.0.0.1',
            action='login_failed',
        )
        self.assertEqual(attempt.severity, 'info')

    def test_invalidated_defaults_to_false(self):
        attempt = AuthLog.objects.create(
            user=None,
            username='ktos',
            ip_address='127.0.0.1',
            action='login_failed',
        )
        self.assertFalse(attempt.invalidated)

    def test_timestamp_auto_now_add(self):
        before = timezone.now()
        attempt = AuthLog.objects.create(
            user=self.user,
            username=None,
            ip_address='127.0.0.1',
            action='login_success',
        )
        after = timezone.now()
        self.assertTrue(before <= attempt.timestamp <= after)

    def test_str_representation(self):
        attempt = AuthLog.objects.create(
            user=self.user,
            username='jan_kowalski',
            ip_address='127.0.0.1',
            action='login_success',
        )
        text = str(attempt)
        self.assertIn('jan_kowalski', text)
        self.assertIn('login_success', text)

    def test_deleting_user_sets_null(self):
        # on_delete=SET_NULL - usuniecie usera nie kasuje logu
        attempt = AuthLog.objects.create(
            user=self.user,
            username=None,
            ip_address='127.0.0.1',
            action='login_success',
        )
        self.user.delete()
        attempt.refresh_from_db()
        self.assertIsNone(attempt.user)

    def test_ip_address_nullable(self):
        attempt = AuthLog.objects.create(
            user=self.user,
            username=None,
            ip_address=None,
            action='login_success',
        )
        self.assertIsNone(attempt.ip_address)

    def test_ordering_most_recent_first(self):
        old = AuthLog.objects.create(
            user=self.user, username=None,
            ip_address='127.0.0.1', action='login_success',
        )
        old.timestamp = timezone.now() - timedelta(hours=1)
        old.save(update_fields=['timestamp'])

        new = AuthLog.objects.create(
            user=self.user, username=None,
            ip_address='127.0.0.1', action='login_success',
        )

        attempts = list(AuthLog.objects.all())
        self.assertEqual(attempts[0].pk, new.pk)
        self.assertEqual(attempts[1].pk, old.pk)


class LoginLockoutTests(TestCase):
    """Testy mechanizmu lockout po N nieudanych probach (per IP)."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(
            username='jan_kowalski',
            password='TajneHaslo123!',
            is_active=True,
        )

    def _fail_login(self, username='jan_kowalski', password='zle_haslo', ip='127.0.0.1'):
        return self.client.post(
            self.login_url,
            {'username': username, 'password': password},
            REMOTE_ADDR=ip,
        )

    def test_successful_login_creates_success_log(self):
        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        entry = AuthLog.objects.filter(action='login_success').latest('timestamp')
        self.assertEqual(entry.user, self.user)

    def test_failed_login_creates_failed_log(self):
        self._fail_login()
        entry = AuthLog.objects.filter(action='login_failed').latest('timestamp')
        self.assertEqual(entry.user, self.user)  # user istnieje, wiec przypisany po userze

    def test_login_allowed_below_threshold(self):
        # N-1 nieudanych prob - IP jeszcze NIE zablokowane
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            self._fail_login()

        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.assertRedirects(response, reverse('home'))

    def test_lockout_triggers_after_n_failed_attempts(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login()

        # Kolejna proba - nawet z poprawnym haslem - powinna zostac zablokowana
        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.assertEqual(response.status_code, 200)  # nie redirect
        self.assertContains(response, 'Zbyt wiele prób logowania.')

    def test_locked_out_user_not_authenticated(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login()

        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_lockout_creates_ip_locked_entry(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login()

        self.assertTrue(
            AuthLog.objects.filter(action='ip_locked', ip_address='127.0.0.1').exists()
        )

    def test_lockout_blocks_further_attempts_without_new_failed_logs(self):
        # Gdy blokada jest juz aktywna, widok NIE powinien zapisywac kolejnych logow
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login()

        count_before = AuthLog.objects.count()

        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })

        count_after = AuthLog.objects.count()
        self.assertEqual(count_before, count_after)

    def test_lockout_is_per_ip_blocks_other_users_too(self):
        # Blokada dziala na poziomie IP, wiec inny user z tego samego IP
        # rowniez zostanie zablokowany.
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login(username='jan_kowalski')

        User.objects.create_user(username='anna_nowak', password='InneHaslo456!', is_active=True)
        response = self.client.post(self.login_url, {
            'username': 'anna_nowak',
            'password': 'InneHaslo456!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Zbyt wiele prób logowania.')

    def test_same_user_different_ip_not_blocked(self):
        # Nieudane proby z jednego IP nie blokuja tego samego usera z innego IP
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login(ip='127.0.0.1')

        response = self.client.post(
            self.login_url,
            {'username': 'jan_kowalski', 'password': 'TajneHaslo123!'},
            REMOTE_ADDR='10.0.0.9',
        )
        self.assertRedirects(response, reverse('home'))

    def test_old_failed_attempts_outside_window_do_not_count(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._fail_login()

        old_time = timezone.now() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES + 1)
        AuthLog.objects.filter(action='login_failed').update(timestamp=old_time)

        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.assertRedirects(response, reverse('home'))

    def test_inactive_user_counts_as_failed_attempt(self):
        self.user.is_active = False
        self.user.save()

        for _ in range(MAX_FAILED_ATTEMPTS):
            response = self.client.post(self.login_url, {
                'username': 'jan_kowalski',
                'password': 'TajneHaslo123!',  # poprawne haslo, ale konto nieaktywne
            })
            # authenticate() zwraca None dla is_active=False -> form.is_valid() == False
            # -> galaz "invalid form" -> nadpisany komunikat 'Błędne dane.'
            self.assertContains(response, 'Błędne dane.')

        failed_count = AuthLog.objects.filter(action='login_failed').count()
        self.assertEqual(failed_count, MAX_FAILED_ATTEMPTS)

    def test_invalid_form_counts_as_failed_attempt(self):
        # Pusty username/password - form.is_valid() == False, existing_user == None
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.client.post(self.login_url, {'username': '', 'password': ''})

        count = AuthLog.objects.filter(action='login_failed', user__isnull=True).count()
        self.assertEqual(count, MAX_FAILED_ATTEMPTS)

    def test_successful_login_invalidates_previous_failed_logs(self):
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            self._fail_login()

        response = self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.assertRedirects(response, reverse('home'))

        all_failed = AuthLog.objects.filter(action='login_failed', ip_address='127.0.0.1')
        self.assertEqual(all_failed.count(), MAX_FAILED_ATTEMPTS - 1)

        # wszystkie oznaczone jako invalidated
        self.assertTrue(all(a.invalidated for a in all_failed))

        self.client.get(reverse('logout'))

        # Kolejna nieudana proba nie powinna od razu wywolac lockout
        response2 = self._fail_login()
        self.assertContains(response2, 'Błędne dane.')
        self.assertNotContains(response2, 'Zbyt wiele prób logowania.')

    def test_invalidated_logs_are_not_deleted(self):
        self._fail_login()
        self._fail_login()

        count_before = AuthLog.objects.count()

        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })

        count_after = AuthLog.objects.count()
        # Rekordy nadal istnieja + doszedl nowy log login_success
        self.assertEqual(count_after, count_before + 1)

    def test_invalidated_true_after_successful_login(self):
        self._fail_login()
        entry = AuthLog.objects.filter(action='login_failed').first()
        self.assertFalse(entry.invalidated)

        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })

        entry.refresh_from_db()
        self.assertTrue(entry.invalidated)

    def test_reset_does_not_affect_other_ip_failed_attempts(self):
        User.objects.create_user(username='anna_nowak', password='InneHaslo456!', is_active=True)

        # Nieudane proby dla anna_nowak z innego IP
        self.client.post(
            self.login_url,
            {'username': 'anna_nowak', 'password': 'zle'},
            REMOTE_ADDR='10.0.0.1',
        )
        self.client.post(
            self.login_url,
            {'username': 'anna_nowak', 'password': 'zle'},
            REMOTE_ADDR='10.0.0.1',
        )

        # Udane logowanie jan_kowalski z IP 127.0.0.1
        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })

        # Nieudane proby anny (inne IP) powinny nadal byc nieinwalidowane
        anna_failed = AuthLog.objects.filter(
            ip_address='10.0.0.1', action='login_failed', invalidated=False,
        )
        self.assertEqual(anna_failed.count(), 2)

    def test_logout_creates_logout_log(self):
        self.client.post(self.login_url, {
            'username': 'jan_kowalski',
            'password': 'TajneHaslo123!',
        })
        self.client.get(reverse('logout'))

        entry = AuthLog.objects.filter(action='logout').latest('timestamp')
        self.assertEqual(entry.user, self.user)
        self.assertIsNone(entry.username)