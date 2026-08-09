from django.test import TestCase
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from leaves.models import WorkerProfile


class ReportsAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin_test', password='test123', role='Admin')
        self.hr = User.objects.create_user(username='hr_test', password='test123', role='HR')
        self.manager = User.objects.create_user(username='manager_test', password='test123', role='Manager')
        self.worker = User.objects.create_user(username='worker_test', password='test123', role='Worker')

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_role'] = user.role
        session.save()

    def test_users_per_role_admin_access(self):
        self._login(self.admin)
        response = self.client.get(reverse('users_per_role_report'))
        self.assertEqual(response.status_code, 200)

    def test_users_per_role_worker_denied(self):
        self._login(self.worker)
        response = self.client.get(reverse('users_per_role_report'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'leaves/access_denied.html')

    def test_leave_usage_hr_access(self):
        self._login(self.hr)
        response = self.client.get(reverse('leave_usage_report'))
        self.assertEqual(response.status_code, 200)

    def test_leave_usage_worker_denied(self):
        self._login(self.worker)
        response = self.client.get(reverse('leave_usage_report'))
        self.assertTemplateUsed(response, 'leaves/access_denied.html')

    def test_team_report_manager_access(self):
        WorkerProfile.objects.create(user=self.manager, team='A', hire_date='2020-01-01')
        self._login(self.manager)
        response = self.client.get(reverse('team_report'))
        self.assertEqual(response.status_code, 200)

    def test_api_leave_usage_returns_json(self):
        self._login(self.admin)
        response = self.client.get(reverse('api_leave_usage'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_api_users_per_role_worker_denied(self):
        self._login(self.worker)
        response = self.client.get(reverse('api_users_per_role'))
        self.assertEqual(response.status_code, 403)