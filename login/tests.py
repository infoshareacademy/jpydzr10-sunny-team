from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User


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


    #  TEST 1: GET --> 200
    #  czy strona logowania się otwiera?
    # kod 200 - ok

    def test_get_login_page_returns_200(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')


    #  TEST 2: Błędne dane --> zostajemy na stronie logowania
    #  kod 200
    def test_post_wrong_credentials_stays_on_login(self):
        response = self.client.post(self.login_url, {
            'username': 'Jan_A',
            'password': 'ZLE_HASLO',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


    #  TEST 3: Poprawne dane --> przekierowanie (kod 302)
    #  po poprawnym zalogowaniu django powinno przekierować na dashboard (od 302)
    def test_post_correct_credentials_redirects(self):
        response = self.client.post(self.login_url, {
            'username': 'Jan_A',
            'password': 'haslo123',
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)


    #  TEST 4: Konto nieaktywne --> odmowa logowania (bez względu na dobre/złe hasło)

    def test_post_inactive_user_cannot_login(self):
        response = self.client.post(self.login_url, {
            'username': 'Stefan_Z',
            'password': 'innehaslo123',  # hasło poprawne, ale konto nieaktywne
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


    #  TEST 5: Hasło krótsze niż 6 znaków --> odmowa

    def test_post_password_too_short_cannot_login(self):
        response = self.client.post(self.login_url, {
            'username': 'Jan_A',
            'password': 'abc',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
