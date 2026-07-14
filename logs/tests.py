from datetime import date, timedelta
from django.contrib.admin.sites import AdminSite
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone as dj_timezone

from accounts.models import User
from leaves.models import LeaveRequest, WorkerProfile
from logs.admin import ChangeLogAdmin
from logs.models import ActivityLog, AuthLog


class ChangeLogAdminTests(TestCase):
    """Testy panelu admina dla ActivityLog - ma byc wylacznie do odczytu."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = ChangeLogAdmin(ActivityLog, self.site)
        self.user = User.objects.create_user(username='ktos', password='haslo123')
        self.log_entry = ActivityLog.objects.create(
            who=self.user,
            action='create',
            object_type='user',
            object_id=self.user.id,
        )

    def test_readonly_fields(self):
        self.assertEqual(
            self.admin.readonly_fields,
            ["who", "action", "object_type", "created_at"],
        )

    def test_has_add_permission_is_false(self):
        self.assertFalse(self.admin.has_add_permission(request=None))

    def test_has_change_permission_is_false_without_obj(self):
        self.assertFalse(self.admin.has_change_permission(request=None))

    def test_has_change_permission_is_false_with_obj(self):
        self.assertFalse(self.admin.has_change_permission(request=None, obj=self.log_entry))


class LeaveRequestSignalTests(TestCase):
    """Testy sygnałów pre_save/post_save tworzących wpisy w ActivityLog."""

    def setUp(self):
        self.employee = User.objects.create_user(username='pracownik', password='haslo123')
        self.confirmer = User.objects.create_user(
            username='szef', password='haslo123', role='Admin',
        )

    def test_creating_request_logs_create_action(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            amount_days=2,
        )

        entry = ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).latest('created_at')
        self.assertEqual(entry.action, 'create')
        self.assertEqual(entry.who, self.employee)

    def test_updating_pending_request_logs_update_action(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            amount_days=2,
        )
        ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).delete()

        leave_request.change_request(date(2026, 9, 3), date(2026, 9, 4))

        entry = ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).latest('created_at')
        self.assertEqual(entry.action, 'update')
        self.assertEqual(entry.who, self.employee)

    def test_approving_request_logs_approve_action_with_who_confirmed(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            amount_days=2,
        )
        ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).delete()

        leave_request.approve(self.confirmer)

        entry = ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).latest('created_at')
        self.assertEqual(entry.action, 'approve')
        self.assertEqual(entry.who, self.confirmer)

    def test_rejecting_request_logs_reject_action_with_who_confirmed(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            amount_days=2,
        )
        ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).delete()

        leave_request.reject(self.confirmer)

        entry = ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).latest('created_at')
        self.assertEqual(entry.action, 'reject')
        self.assertEqual(entry.who, self.confirmer)

    def test_canceling_request_logs_cancel_action_with_who_confirmed(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            amount_days=2,
        )
        ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).delete()

        leave_request.cancel_request(self.employee)

        entry = ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).latest('created_at')
        self.assertEqual(entry.action, 'cancel')
        self.assertEqual(entry.who, self.employee)

    def test_status_change_without_matching_action_is_not_logged(self):
        # PENDING -> PENDING jest juz osobno obsluzone jako 'update';
        # sprawdzamy ze zmiana pol niebedacych statusem tez nie tworzy duplikatow
        # innych akcji niz 'update'.
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            amount_days=2,
        )
        ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).delete()

        leave_request.amount_days = 3
        leave_request.save()

        entry = ActivityLog.objects.filter(
            object_type='leave_request', object_id=leave_request.id,
        ).latest('created_at')
        self.assertEqual(entry.action, 'update')


class LogViewsTestCase(TestCase):
    """Wspolny setUp dla testow widokow activity_log_history i auth_log_history."""

    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in ["Admin", "HR", "Manager", "Worker"]:
            cls.users[role] = User.objects.create_user(
                username=f"log_{role.lower()}",
                password="testpass123",
                role=role,
            )
        for role in ["Manager", "Worker"]:
            WorkerProfile.objects.create(
                user=cls.users[role],
                team="a",
                hire_date=date(2024, 1, 1),
            )

    def login_as(self, role):
        self.client.login(username=f"log_{role.lower()}", password="testpass123")


class ActivityLogViewTests(LogViewsTestCase):

    def setUp(self):
        self.url = reverse('activity_log')
        ActivityLog.objects.create(
            who=self.users['Admin'], action='create',
            object_type='leave_request', object_id=1,
        )
        ActivityLog.objects.create(
            who=self.users['HR'], action='approve',
            object_type='leave_request', object_id=2,
        )

    # can_view_logs: True dla Admin/HR, False dla Manager/Worker
    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_role_without_permission_is_redirected(self):
        self.login_as('Worker')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('dashboard'))

    def test_role_with_permission_gets_200(self):
        self.login_as('Admin')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_role_without_permission_creates_auth_log_entry(self):
        self.login_as('Manager')
        self.client.get(self.url)
        self.assertTrue(
            AuthLog.objects.filter(user=self.users['Manager']).exists()
        )

    def test_filter_by_action(self):
        self.login_as('Admin')
        response = self.client.get(self.url, {'action': 'approve'})
        logs = list(response.context['logs'])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, 'approve')

    def test_filter_by_object_type(self):
        self.login_as('Admin')
        response = self.client.get(self.url, {'object_type': 'leave_request'})
        self.assertEqual(len(response.context['logs']), 2)

    def test_filter_by_user(self):
        self.login_as('Admin')
        response = self.client.get(self.url, {'user': self.users['HR'].id})
        logs = list(response.context['logs'])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].who, self.users['HR'])

    def test_filter_by_user_invalid_value_is_ignored(self):
        self.login_as('Admin')
        response = self.client.get(self.url, {'user': 'not-a-number'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['logs']), 2)

    def test_filter_by_date_range(self):
        self.login_as('Admin')

        # Bazujemy na realnej dacie zapisanego rekordu (po konwersji na lokalna
        # strefe), a nie na zalozeniu ze timezone.localdate() w tescie da
        # dokladnie to samo co baza wyliczy w zapytaniu __date__gte/lte.
        entry = ActivityLog.objects.latest('created_at')
        entry_local_date = dj_timezone.localtime(entry.created_at).date()

        response = self.client.get(self.url, {
            'date_from': entry_local_date.isoformat(),
            'date_to': entry_local_date.isoformat(),
        })
        self.assertEqual(len(response.context['logs']), 2)

        future = (entry_local_date + timedelta(days=1)).isoformat()
        response = self.client.get(self.url, {'date_from': future})
        self.assertEqual(len(response.context['logs']), 0)

    def test_pagination_limits_to_20_per_page(self):
        for i in range(25):
            ActivityLog.objects.create(
                who=self.users['Admin'], action='create',
                object_type='leave_request', object_id=100 + i,
            )
        self.login_as('Admin')
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['logs']), 20)

        response_page2 = self.client.get(self.url, {'page': 2})
        self.assertEqual(len(response_page2.context['logs']), 7)  # 25 + 2 z setUp - 20


class AuthLogViewTests(LogViewsTestCase):

    def setUp(self):
        self.url = reverse('auth_log')
        AuthLog.objects.create(
            user=self.users['Worker'], username=None, ip_address='127.0.0.1',
            action='login_success', severity='info',
        )
        AuthLog.objects.create(
            user=None, username='nieznany', ip_address='10.0.0.1',
            action='login_failed', severity='warning',
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_role_without_permission_is_redirected(self):
        self.login_as('Manager')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('dashboard'))

    def test_role_with_permission_gets_200(self):
        self.login_as('HR')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_filter_by_action(self):
        self.login_as('Admin')
        response = self.client.get(self.url, {'action': 'login_failed'})
        logs = list(response.context['logs'])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, 'login_failed')

    def test_filter_by_severity(self):
        self.login_as('Admin')
        response = self.client.get(self.url, {'severity': 'warning'})
        logs = list(response.context['logs'])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].severity, 'warning')

    def test_filter_by_user(self):
        self.login_as('Admin')
        response = self.client.get(self.url, {'user': self.users['Worker'].id})
        logs = list(response.context['logs'])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].user, self.users['Worker'])

    def test_filter_by_user_invalid_value_is_ignored(self):
        self.login_as('Admin')
        response = self.client.get(self.url, {'user': 'abc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['logs']), 2)

    def test_filter_by_date_range_uses_full_day_bounds(self):
        self.login_as('Admin')
        today = dj_timezone.localdate().isoformat()
        response = self.client.get(self.url, {'date_from': today, 'date_to': today})
        self.assertEqual(len(response.context['logs']), 2)

        yesterday = (dj_timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.client.get(self.url, {'date_from': yesterday, 'date_to': yesterday})
        self.assertEqual(len(response.context['logs']), 0)

    def test_pagination_limits_to_20_per_page(self):
        for i in range(25):
            AuthLog.objects.create(
                user=self.users['Admin'], username=None, ip_address='127.0.0.1',
                action='login_success', severity='info',
            )
        self.login_as('Admin')
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['logs']), 20)

        response_page2 = self.client.get(self.url, {'page': 2})
        self.assertEqual(len(response_page2.context['logs']), 7)  # 25 + 2 z setUp - 20