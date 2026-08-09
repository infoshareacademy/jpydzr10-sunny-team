from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import format_lazy
from django.views.generic import DetailView
from .forms import WorkerProfileForm, ROLE_ASSIGNMENT_PERMISSIONS, EditUserForm
from leaves.models import WorkerProfile, LeaveRequest
from .permission import Permission
from accounts.permission import role_required
from logs.models import AuthLog, ActivityLog
from logs.utils import get_client_ip
from django.contrib.auth import get_user_model, update_session_auth_hash
from accounts.forms import AddUserForm
from datetime import date, timedelta
from django.conf import settings
from mail.utils import send_deactivation_email
from leaves.utils import Calendar_utils
from django.core.paginator import Paginator
from django.db.models import Case, When, Value, IntegerField, Q
from accounts.models import User
from team.models import Team
from django.utils.translation import gettext_lazy as _


@login_required
def deactivate_user(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if request.user == target_user:
        messages.error(request, _('Nie możesz dezaktywować własnego konta.'))
        return redirect('user_list')

    if request.method == 'POST':
        target_user.is_active = False
        target_user.save()

        if target_user.email:
            send_deactivation_email(
                user_email=target_user.email,
                user_name=f"{target_user.first_name} {target_user.last_name}",
                site_url=settings.SITE_URL,
            )

        messages.success(request, format_lazy(_('Użytkownik {username} został dezaktywowany.'),username=target_user.username))
        return redirect('user_list')

    return render(request, 'accounts/deactivate_user.html', {'target_user': target_user})

@login_required
@role_required('can_view_user_list')
def user_list(request):
    viewer = request.user
    active_role = request.session.get('active_role', viewer.role)

    role_order = Case(
        When(role='Admin', then=0),
        When(role='Manager', then=1),
        When(role='HR', then=2),
        When(role='Worker', then=3),
        default=4,
        output_field=IntegerField(),
    )

    base_qs = User.objects.exclude(role='Admin').exclude(is_superuser=True)

    if active_role == 'Admin':
        users = base_qs
    elif active_role in ('Manager', 'HR'):
        managed_team_ids = Team.objects.for_user(viewer).values_list('pk', flat=True)
        users = base_qs.filter(worker_profile__team_id__in=managed_team_ids, is_active=True)
    else:
        messages.info(request, _('Nie masz uprawnień do przeglądania listy użytkowników.'))
        return redirect('home')

    # Filtr wyszukiwania
    search_query = request.GET.get('search', '').strip()
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query)
        )

    # Filtr zespołu dla HR
    selected_team_id = ''
    if active_role == 'HR':
        selected_team_id = request.GET.get('team', '').strip()
        if selected_team_id.isdigit():
            users = users.filter(worker_profile__team_id=selected_team_id)

    # Filtry dla Admina
    selected_status = ''
    selected_role = request.GET.get('role', '')
    no_team_only = False
    no_profile_only = False

    if active_role == 'Admin':
        selected_status = request.GET.get('status', '').strip()
        if selected_status == 'active':
            users = users.filter(is_active=True)
        elif selected_status == 'inactive':
            users = users.filter(is_active=False)

        no_team_only = request.GET.get('no_team') == '1'
        if no_team_only:
            users = users.filter(
                Q(worker_profile__isnull=True) | Q(worker_profile__team__isnull=True)
            )

        no_profile_only = request.GET.get('no_profile') == '1'
        if no_profile_only:
            users = users.filter(worker_profile__isnull=True)

        if selected_role:
            users = users.filter(role=selected_role)

    users = users.annotate(role_order=role_order).order_by(
        '-is_active', 'role_order', 'last_name', 'first_name'
    ).select_related('worker_profile', 'worker_profile__team').distinct()

    # Wyciągnięcie zespołów zarządzanych przez każdego z użytkowników
    user_list_data = list(users)
    for u in user_list_data:
        # Sprawdzamy, czy użytkownik jest wpisany jako manager lub hr w danym zespole
        managed_by_user = Team.objects.filter(
            Q(manager_id=u.id) | Q(hr_id=u.id)
        ).distinct()
        u.managed_teams_list = list(managed_by_user)

    context = {
        'users': user_list_data,
        'active_role': active_role,
        'search_query': search_query,
        'managed_teams': (
            Team.objects.for_user(viewer) if active_role in ('Manager', 'HR') else Team.objects.none()
        ),
        'selected_team_id': int(selected_team_id) if selected_team_id.isdigit() else '',
        'selected_status': selected_status,
        'no_team_only': no_team_only,
        'no_profile_only': no_profile_only,
    }
    return render(request, 'accounts/user_list.html', context)

@login_required
def switch_role(request):
    from accounts.context_processors import ALLOWED_ROLES
    new_role = request.POST.get("role")
    old_role = request.session.get('active_role', request.user.role)
    if new_role in ALLOWED_ROLES.get(request.user.role, []):
        request.session['active_role'] = new_role
        messages.success(request, format_lazy(_("Zmieniono aktywną rolę z {old_role} na {new_role}."), old_role=old_role, new_role=new_role))
        AuthLog.objects.create(
            user=request.user,
            action='role_change',
            severity='info',
            details=format_lazy(_("Zmieniono aktywną rolę z {old_role} na {new_role}."), old_role=old_role, new_role=new_role),
            ip_address=get_client_ip(request),
        )
        return redirect('home')

    elif  new_role == old_role:
        messages.info(request, format_lazy(_("Jesteś już w roli: {new_role}"),new_role=new_role))
        return redirect('home')

    else:
        messages.error(request, _('Nie masz uprawnień do tej roli'))
        AuthLog.objects.create(
            user=request.user,
            action='access_denied_403',
            severity='warning',
            details=format_lazy(_("Proba zmiany roli na: {new_role}"), new_role=new_role),
            ip_address=get_client_ip(request),
        )
        return redirect('home')


def _render_profile_form(request, target_user, allowed_roles, instance, template):
    """Wspólna logika GET/POST dla assign i edit z blokadą edycji własnego profilu."""
    current_user_role = request.session.get('active_role', request.user.role)
    if request.user == target_user:
        messages.error(request, _('Nie możesz edytować własnego profilu.'))
        return redirect('user_list')

    is_new = instance is None

    if request.method == 'POST':
        form = WorkerProfileForm(
            request.POST,
            allowed_roles=allowed_roles,
            target_user=target_user,
            instance=instance,
            user_role=current_user_role,
        )
        if form.is_valid():
            form.save()
            action_type = 'create' if is_new else 'update'
            if is_new:
                details_msg = format_lazy(_('Utworzono profil użytkownika: {username}'), username=target_user.username)
            else:
                details_msg = format_lazy(_('Zaktualizowano profil użytkownika: {username}'),
                                          username=target_user.username)

            ActivityLog.objects.create(
                who=request.user,
                action=action_type,
                object_type='worker_profile',
                object_id=target_user.id,
                details=details_msg,
            )
            messages.success(request, details_msg)
            return redirect('profile', user_id=target_user.id)
    else:
        form = WorkerProfileForm(
            allowed_roles=allowed_roles,
            target_user=target_user,
            instance=instance,
            user_role=current_user_role
        )

    return render(request, template, {'form': form, 'target_user': target_user})


@login_required
@role_required("can_add_user")
def add_user(request):
    if request.method == 'POST':
        form = AddUserForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            ActivityLog.objects.create(
                who=request.user,
                action='create',
                object_type='user',
                object_id=new_user.id,
                details=format_lazy(_('Utworzono nowego użytkownika: {new_username}'), new_username=new_user.username),
            )
            messages.success(
                request,
                format_lazy(_('Konto {new_username} zostało utworzone.'), new_username=new_user.username),
            )
            return redirect('assign_worker_profile', user_id=new_user.id)
    else:
        form = AddUserForm()

    return render(request, 'accounts/add_user.html', {'form': form})

@login_required
@role_required("can_add_user")
def edit_user(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)


    if request.method == 'POST':
        form = EditUserForm(request.POST, instance=target_user)
        if form.is_valid():
            updated_user = form.save()

            ActivityLog.objects.create(
                who=request.user,
                action='update',
                object_type='user',
                object_id=updated_user.id,
                details=format_lazy(_('Zaktualizowano dane podstawowe użytkownika: {updated_username}'), updated_username=updated_user.username),
            )

            messages.success(
                request,
                format_lazy(_('Dane użytkownika {updated_username} zostały zaktualizowane.'),updated_username=updated_user.username),
            )
            return redirect('profile', user_id=updated_user.id)
    else:
        form = EditUserForm(instance=target_user)

    return render(
        request,
        'accounts/edit_user.html',
        {
            'form': form,
            'target_user': target_user,
        }
    )


@login_required
@role_required("can_manage_worker")
def assign_worker_profile(request, user_id):
    """Tworzy WorkerProfile i nadaje rolę użytkownikowi, który go jeszcze nie ma."""
    target_user = get_object_or_404(User, id=user_id)

    if WorkerProfile.objects.filter(user=target_user).exists():
        return redirect('edit_worker_profile', user_id=target_user.id)

    active_role = request.session.get('active_role', request.user.role)
    allowed_roles = ROLE_ASSIGNMENT_PERMISSIONS.get(active_role, [])

    return _render_profile_form(
        request, target_user, allowed_roles, instance=None, template='accounts/assign_worker_profile.html'
    )


@login_required
@role_required("can_manage_worker")
def edit_worker_profile(request, user_id):
    """Edytuje istniejący WorkerProfile oraz rolę użytkownika."""
    target_user = get_object_or_404(User, id=user_id)

    if not target_user.is_active:
        messages.error(request, _("Nie można edytować profilu nieaktywnego użytkownika."))
        return redirect('home')

    existing_profile = WorkerProfile.objects.filter(user=target_user).first()

    if not existing_profile:
        return redirect('assign_worker_profile', user_id=target_user.id)

    active_role = request.session.get('active_role', request.user.role)
    allowed_roles = ROLE_ASSIGNMENT_PERMISSIONS.get(active_role, [])

    return _render_profile_form(
        request, target_user, allowed_roles, instance=existing_profile, template='accounts/edit_worker_profile.html'
    )

@login_required
def change_own_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)

            AuthLog.objects.create(
                user=request.user,
                action='password_changed',
                severity='info',
                details=_("Zmieniono własne hasło."),
                ip_address=get_client_ip(request),
            )

            messages.success(request, _("Twoje hasło zostało pomyślnie zmienione."))
            return redirect("profile", user_id=request.user.id)
        else:
            messages.error(
                request, _("Niepoprawne dane w formularzu.")
            )
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, "accounts/change_own_password.html", {"form": form})

MONTH_NAMES_PL = [_('Sty'), _('Lut'), _('Mar'), _('Kwi'), _('Maj'), _('Cze'), _('Lip'), _('Sie'), _('Wrz'), _('Paź'), _('Lis'), _('Gru')]

class ProfileView(LoginRequiredMixin, DetailView):
    model = WorkerProfile
    template_name = 'accounts/profile.html'
    context_object_name = 'profile'

    def get(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')
        target_user = get_object_or_404(User, pk=user_id) if user_id else request.user

        try:
            profile = WorkerProfile.objects.select_related('team').get(user=target_user)
        except WorkerProfile.DoesNotExist:
            messages.error(request, format_lazy(_('Użytkownik {target_username} nie ma przypisanego profilu.'), target_username=target_user.username))
            return redirect('home')

        active_role = request.session.get('active_role', request.user.role)
        position = target_user.role

        if not self._has_access(request.user, target_user, active_role):
            self._log_access_denied(request, target_user, active_role)
            messages.info(request, _('Nie masz uprawnień do przeglądania tego profilu'))
            return redirect('home')

        self.object = profile
        context = self.get_context_data(
            object=profile,
            target_user=target_user,
            active_role=active_role,
            position=position,
        )
        return self.render_to_response(context)

    def _log_access_denied(self, request, target_user, active_role):
        AuthLog.objects.create(
            user=request.user,
            action='access_denied_403',
            details=format_lazy(
                _("Próba podglądu profilu {target_username} (id={target_id}). Aktywna rola: {active_role}"),
                target_username=target_user.username,
                target_id=target_user.id,
                active_role=active_role,
            ),
            ip_address=get_client_ip(request),
            severity='warning',
        )

    def _has_access(self, viewer, target_user, active_role):
        """
        - Własny profil -> zawsze DOSTĘP
        - Admin -> zawsze DOSTĘP
        - Manager / HR -> dostęp TYLKO gdy target_user należy do zespołu, którym zarządzają
        """
        if target_user == viewer:
            return True

        if active_role == 'Admin':
            return True

        if active_role in ['Manager', 'HR']:
            if not target_user.is_active:
                return False
            return self._is_user_in_managed_teams(viewer, target_user)

        return False

    def _is_user_in_managed_teams(self, viewer, target_user) -> bool:
        try:
            target_team_id = target_user.worker_profile.team_id
        except WorkerProfile.DoesNotExist:
            return False

        if not target_team_id:
            return False

        managed_team_ids = Team.objects.for_user(viewer).values_list('pk', flat=True)
        return target_team_id in managed_team_ids

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_user = kwargs['target_user']
        active_role = kwargs['active_role']
        position = kwargs['position']
        profile = self.object

        context['profile_owner'] = target_user
        context['is_own_profile'] = (self.request.user == target_user)
        context['is_admin'] = (active_role == 'Admin')
        context['active_role'] = active_role
        context['position'] = position

        self._add_leave_balance_context(context, profile)
        self._add_team_context(context, profile, target_user)
        self._add_chart_context(context, target_user)
        self._add_requests_context(context, target_user, active_role)
        self._add_activity_log_context(context, target_user, active_role)

        return context

    def _add_leave_balance_context(self, context, profile):
        try:
            total_days = profile._get_total_leave_days()
            used_days = profile.used_leave_days
            remaining_days = profile.get_leave_days()
            progress_percent = round((used_days / total_days) * 100) if total_days > 0 else 0
        except (WorkerProfile.DoesNotExist, AttributeError, TypeError, ZeroDivisionError):
            total_days = used_days = remaining_days = None
            progress_percent = 0

        context['total_days'] = total_days
        context['used_days'] = used_days
        context['remaining_days'] = remaining_days
        context['progress_percent'] = progress_percent

    def _add_team_context(self, context, profile, target_user):
        """
        - team: zespół profilowanego użytkownika
        - worker_team_name: jego nazwa
        - managed_teams: zespoły, którymi zarządza WŁAŚCICIEL profilu (jeśli HR/Manager)
        - accessible_team_ids: zespoły, którymi zarządza OSOBA PRZEGLĄDAJĄCA (self.request.user)
          -> tylko do nich pokazujemy link w szablonie
        """
        user_team = profile.team if profile else None
        context['team'] = user_team
        context['worker_team_name'] = user_team.name if user_team else None

        target_user_role = target_user.role
        if target_user_role in ['HR', 'Manager']:
            context['managed_teams'] = Team.objects.active().for_user(target_user)
        else:
            context['managed_teams'] = Team.objects.none()

        context['accessible_team_ids'] = set(
            Team.objects.for_user(self.request.user).values_list('pk', flat=True)
        )

    def _add_chart_context(self, context, target_user):
        current_year = date.today().year
        cal = Calendar_utils(current_year)

        monthly_days = [0] * 12
        approved_leaves = LeaveRequest.objects.filter(
            employee=target_user,
            status=LeaveRequest.Status.APPROVED,
            start_date__year__lte=current_year,
            end_date__year__gte=current_year,
        )

        for leave in approved_leaves:
            range_start = max(leave.start_date, date(current_year, 1, 1))
            range_end = min(leave.end_date, date(current_year, 12, 31))

            current = range_start
            while current <= range_end:
                if cal.is_working_day(current):
                    monthly_days[current.month - 1] += 1
                current += timedelta(days=1)

        context['current_year'] = current_year
        context['chart_labels'] = MONTH_NAMES_PL
        context['chart_values'] = monthly_days
        context['chart_max'] = context.get('total_days') or 26

    def _add_requests_context(self, context, target_user, active_role):
        target_requests = LeaveRequest.objects.filter(
            employee=target_user,
            end_date__gte=date.today(),
        ).filter(
            Q(status='approved') | Q(status='pending')
        )

        context['recent_requests'] = target_requests.order_by('-created_at')[:5]
        context['active_count'] = target_requests.exclude(status=LeaveRequest.Status.CANCELED).count()
        context['pending_count'] = target_requests.filter(status=LeaveRequest.Status.PENDING).count()

    def _add_activity_log_context(self, context, target_user, active_role):
        has_access_to_activity = (
            context['is_own_profile'] or active_role in ['Admin', 'HR', 'Manager']
        )

        if has_access_to_activity:
            context['activity_logs'] = ActivityLog.objects.filter(
                who=target_user,
                object_type='leave_request',
            ).order_by('-created_at')[:6]
        else:
            context['activity_logs'] = []
