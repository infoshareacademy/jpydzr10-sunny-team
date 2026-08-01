from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
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


@login_required
def deactivate_user(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if request.user == target_user:
        messages.error(request, 'Nie możesz dezaktywować własnego konta.')
        return redirect('user_list')

    required_action = (
        'can_deactivate_staff'
        if target_user.role in ('Admin', 'COO', 'HR') or target_user.is_superuser
        else 'can_deactivate_worker'
    )

    if not Permission.verifyPermission(request.user.role, required_action):
        messages.error(request, 'Nie masz uprawnień do dezaktywacji tego konta.')
        return redirect('home')

    if request.method == 'POST':
        target_user.is_active = False
        target_user.save()

        if target_user.email:
            send_deactivation_email(
                user_email=target_user.email,
                user_name=f"{target_user.first_name} {target_user.last_name}",
                site_url=settings.SITE_URL,
            )

        messages.success(request, f'Użytkownik {target_user.username} został dezaktywowany.')
        return redirect('user_list')

    return render(request, 'accounts/deactivate_user.html', {'target_user': target_user})



def _apply_user_filters_and_ordering( qs, filters, request):
    active_role = request.session.get('active_role', request.user.role)

    if active_role == 'Manager':

        managed_team_ids = list(
            request.user.head_managed_teams.values_list('id', flat=True)
        ) + list(
            request.user.co_managed_teams.values_list('id', flat=True)
        )

        qs = qs.filter(
            worker_profile__team_id__in=managed_team_ids,
            is_active=True
        )

        filters['role'] = ''
        filters['status'] = ''

    # Wyszukiwanie frazy
    if query := filters['search']:
        qs = qs.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(username__icontains=query)
        )

    # Filtr roli
    if role := filters['role']:
        qs = qs.filter(role=role)

    # Filtr statusu konta
    if filters['status'] == 'active':
        qs = qs.filter(is_active=True)
    elif filters['status'] == 'inactive':
        qs = qs.filter(is_active=False)

    # Filtr zespołu
    if team_id := filters['team']:
        if active_role == 'Manager':
            managed_team_ids = list(
                request.user.head_managed_teams.values_list('id', flat=True)
            ) + list(
                request.user.co_managed_teams.values_list('id', flat=True)
            )
            if team_id.isdigit() and int(team_id) in managed_team_ids:
                qs = qs.filter(worker_profile__team_id=team_id)
        else:
            qs = qs.filter(
                Q(worker_profile__team_id=team_id) |
                Q(head_managed_teams__id=team_id) |
                Q(co_managed_teams__id=team_id),
                is_active=True
            ).distinct()

    # Priorytetyzacja ról i statusu profilu
    # 0 = Brak profilu, 1 = COO, 2 = HR, 3 = Manager, 4 = Worker
    return qs.annotate(
        profile_priority=Case(
            When(worker_profile__isnull=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        role_priority=Case(
            When(role='COO', then=Value(1)),
            When(role='HR', then=Value(2)),
            When(role='Manager', then=Value(3)),
            When(role='Worker', then=Value(4)),
            default=Value(5),
            output_field=IntegerField(),
        )
    ).order_by(
        '-is_active',
        'profile_priority',
        'role_priority',
        'worker_profile__team__name',
        'first_name',
        'last_name'
    )


def _can_see_actions_for(current_user, target_role):
    if current_user.is_superuser or getattr(current_user, 'role', '') in ('COO', 'Admin'):
        return True
    if getattr(current_user, 'role', '') == 'HR':
        return target_role not in ('HR', 'COO', 'Admin')
    return False


def _build_user_sections(page_items, current_user, team_filter):
    active_users = [u for u in page_items if u.is_active]
    inactive_users = [u for u in page_items if not u.is_active] if not team_filter else []
    no_profile_users = [u for u in active_users if not u.has_profile] if not team_filter else []
    with_profile_users = [u for u in active_users if u.has_profile]

    coo_users = [u for u in with_profile_users if u.role == 'COO'] if not team_filter else []
    hr_users = [u for u in with_profile_users if u.role == 'HR'] if not team_filter else []
    manager_users = [u for u in with_profile_users if u.role == 'Manager']
    worker_users = [u for u in with_profile_users if u.role == 'Worker']

    w_unassigned = [
        u for u in worker_users
        if not getattr(u.worker_profile, 'team_id', None)
    ] if not team_filter else []
    teams_map = {}
    for u in worker_users:
        team = getattr(u.worker_profile, 'team', None)
        if team:
            if team.id not in teams_map:
                teams_map[team.id] = {
                    'team': team,
                    'users': []
                }
            teams_map[team.id]['users'].append(u)

    sections = {
        'no_profile': {
            'users': no_profile_users,
            'show_hire_date': False,
            'show_actions': _can_see_actions_for(current_user, 'NO_PROFILE'),
            'has_items': bool(no_profile_users)
        },
        'coo': {
            'users': coo_users,
            'show_hire_date': True,
            'show_actions': _can_see_actions_for(current_user, 'COO'),
            'has_items': bool(coo_users)
        },
        'hr': {
            'users': hr_users,
            'show_hire_date': True,
            'show_actions': _can_see_actions_for(current_user, 'HR'),
            'has_items': bool(hr_users)
        },
        'managers': {
            'users': manager_users,
            'show_hire_date': True,
            'show_actions': _can_see_actions_for(current_user, 'Manager'),
            'has_items': bool(manager_users)
        },
        'workers': {
            'unassigned': w_unassigned,
            'teams': list(teams_map.values()),
            'total_count': len(worker_users),
            'show_hire_date': True,
            'show_actions': _can_see_actions_for(current_user, 'Worker'),
            'has_items': bool(w_unassigned or teams_map)
        }
    }

    return sections, inactive_users


@login_required
@role_required("can_view_user_list")
def user_list(request):
    active_role = request.session.get('active_role', request.user.role)
    filters = {
        'search': request.GET.get('search', '').strip(),
        'role': request.GET.get('role', '').strip(),
        'team': request.GET.get('team', '').strip(),
        'status': request.GET.get('status', '').strip(),
    }
    qs = User.objects.exclude(
        Q(role='Admin') | Q(is_superuser=True) | Q(is_staff=True)
    ).select_related(
        'worker_profile', 'worker_profile__team'
    ).prefetch_related(
        'head_managed_teams', 'co_managed_teams'
    )

    queryset = _apply_user_filters_and_ordering(qs, filters, request    )
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_items = list(page_obj.object_list)
    for u in page_items:
        u.has_profile = hasattr(u, 'worker_profile') and u.worker_profile is not None
        managed_set = set(u.head_managed_teams.all()) | set(u.co_managed_teams.all())
        u.managed_teams = sorted(list(managed_set), key=lambda x: x.name.lower())

    sections, inactive_users = _build_user_sections(page_items, request.user, filters['team'])

    if active_role == 'Manager':
        teams_qs = (
                request.user.head_managed_teams.filter(is_active=True) |
                request.user.co_managed_teams.filter(is_active=True)
        ).distinct().order_by('name')
    else:
        teams_qs = Team.objects.filter(is_active=True).order_by('name')

    context = {
        'page_obj': page_obj,
        'sections': sections,
        'inactive_users': inactive_users,
        'search_query': filters['search'],
        'role_filter': filters['role'],
        'team_filter': filters['team'],
        'status_filter': filters['status'],
        'all_teams_list': teams_qs,
        'all_roles_list': ['Worker', 'Manager', 'HR', 'COO'],
        'current_user_role': getattr(request.user, 'role', ''),
    }

    return render(request, 'accounts/user_list.html', context)

@login_required
def switch_role(request):
    from accounts.context_processors import ALLOWED_ROLES
    new_role = request.POST.get("role")
    old_role = request.session.get('active_role', request.user.role)
    if new_role in ALLOWED_ROLES.get(request.user.role, []):
        request.session['active_role'] = new_role
        messages.success(request, f"Zmieniono aktywną rolę z {old_role} na {new_role}.")
        AuthLog.objects.create(
            user=request.user,
            action='role_change',
            severity='info',
            details=f"Zmieniono aktywną rolę z {old_role} na {new_role}.",
            ip_address=get_client_ip(request),
        )
        return redirect('home')

    elif  new_role == old_role:
        messages.info(request, f"Jesteś już w roli: {new_role}")
        return redirect('home')

    else:
        messages.error(request, 'Nie masz uprawnień do tej roli')
        AuthLog.objects.create(
            user=request.user,
            action='access_denied_403',
            severity='warning',
            details=f"Proba zmiany roli na: {new_role}",
            ip_address=get_client_ip(request),
        )
        return redirect('home')


def _render_profile_form(request, target_user, allowed_roles, instance, template):
    """Wspólna logika GET/POST dla assign i edit z blokadą edycji własnego profilu."""
    if request.user == target_user:
        messages.error(request, 'Nie możesz edytować własnego profilu.')
        return redirect('user_list')

    if request.user.role == 'HR' and target_user.role in 'COO, HR':
        messages.error(request, 'Nie możesz edytować tego profilu.')
        return redirect('user_list')

    is_new = instance is None

    if request.method == 'POST':
        form = WorkerProfileForm(
            request.POST,
            allowed_roles=allowed_roles,
            target_user=target_user,
            instance=instance,
        )
        if form.is_valid():
            form.save()
            action_type = 'create' if is_new else 'update'
            msg_prefix = 'Utworzono' if is_new else 'Zaktualizowano'

            ActivityLog.objects.create(
                who=request.user,
                action=action_type,
                object_type='worker_profile',
                object_id=target_user.id,
                details=f'{msg_prefix} profil użytkownika: {target_user.username}'
            )
            messages.success(request, f'{msg_prefix} profil użytkownika {target_user.username}.')
            return redirect('profile', user_id=target_user.id)
    else:
        form = WorkerProfileForm(
            allowed_roles=allowed_roles,
            target_user=target_user,
            instance=instance,
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
                details=f'Utworzono nowego użytkownika: {new_user.username}'
            )
            messages.success(
                request,
                f'Konto {new_user.username} zostało utworzone.'
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
                details=f'Zaktualizowano dane podstawowe użytkownika: {updated_user.username}'
            )

            messages.success(
                request,
                f'Dane użytkownika {updated_user.username} zostały zaktualizowane.'
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
                details=f"Zmieniono własne hasło.",
                ip_address=get_client_ip(request),
            )

            messages.success(request, "Twoje hasło zostało pomyślnie zmienione.")
            return redirect("profile", user_id=request.user.id)
        else:
            messages.error(
                request, "Niepoprawne dane w formularzu."
            )
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, "accounts/change_own_password.html", {"form": form})

@login_required
@role_required("can_reset_password")
def reset_password(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_password = request.POST.get('new_password')

        if not user_id or not new_password:
            messages.error(request, "Brak ID użytkownika lub hasła.")
            return redirect('reset_password')

        try:
            User = get_user_model()
            user = User.objects.get(id=user_id)

            if len(new_password) < 6:
                messages.error(request, 'Hasło musi mieć co najmniej 6 znaków.')
                return redirect('reset_password')

            user.set_password(new_password)
            user.save()

            ActivityLog.objects.create(
                who=request.user,
                action='password_reset',
                object_type='user',
                object_id=user_id,
                details=f'Zresetowano hasło użytkownika: {user.username}',
            )

            messages.success(request, f'Hasło dla użytkownika {user.username} zostało zresetowane.')
            return redirect('user_list')

        except User.DoesNotExist:
            messages.error(request, 'Nie znaleziono użytkownika.')
        except Exception as e:
            messages.error(request, f'Błąd podczas resetowania hasła: {e}')

    users = User.objects.all()
    return render(request, 'accounts/reset_password.html', {'users': users})

MONTH_NAMES_PL = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru']
class ProfileView(LoginRequiredMixin, DetailView):
    model = WorkerProfile
    template_name = 'accounts/profile.html'
    context_object_name = 'profile'

    def get(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')
        target_user = get_object_or_404(User, pk=user_id) if user_id else request.user

        try:
            profile = WorkerProfile.objects.get(user=target_user)
        except WorkerProfile.DoesNotExist:
            messages.error(request, f'Użytkownik {target_user.username} nie ma przypisanego profilu.')
            return redirect('home')

        active_role = request.session.get('active_role', request.user.role)
        position = target_user.role

        if not self._has_access(request.user, target_user, active_role):
            self._log_access_denied(request, target_user, active_role)
            messages.info(request, 'Nie masz uprawnień do przeglądania tego profilu')
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
            details=(
                f"Próba podglądu profilu {target_user.username} "
                f"(id={target_user.id}). Aktywna rola: {active_role}"
            ),
            ip_address=get_client_ip(request),
            severity='warning',
        )

    def _has_access(self, viewer, target_user, active_role):
        if target_user == viewer:
            return True
        if active_role in ["HR", "COO", "Admin"]:
            return True
        if active_role == 'Manager':
            return self._is_same_team_manager(viewer, target_user)
        return False

    def _is_same_team_manager(self, viewer, target_user):
        if target_user.role != 'Worker':
            return False
        try:
            target_team_id = target_user.worker_profile.team_id
        except WorkerProfile.DoesNotExist:
            return False
        if target_team_id is None:
            return False
        managed_team_ids = Team.get_teams_managed_by(viewer).values_list('pk', flat=True)
        return target_team_id in managed_team_ids

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_user = kwargs['target_user']
        active_role = kwargs['active_role']
        position = kwargs['position']
        profile = self.object

        context['profile_owner'] = target_user
        context['is_own_profile'] = (self.request.user == target_user)
        context['is_admin'] = active_role == 'Admin'
        context['active_role'] = active_role
        context['position'] = position

        self._add_leave_balance_context(context, profile)
        self._add_team_context(context, profile, target_user)
        self._add_chart_context(context, target_user)
        self._add_requests_context(context, target_user)
        self._add_activity_log_context(context, target_user, active_role)

        return context

    def _add_leave_balance_context(self, context, profile):
        try:
            total_days = profile._get_total_leave_days()
            used_days = profile.used_leave_days
            remaining_days = profile.get_leave_days()
            progress_percent = round((used_days / total_days) * 100) if total_days > 0 else 0
        except WorkerProfile.DoesNotExist:
            total_days = used_days = remaining_days = None
            progress_percent = 0

        context['total_days'] = total_days
        context['used_days'] = used_days
        context['remaining_days'] = remaining_days
        context['progress_percent'] = progress_percent

    def _add_team_context(self, context, profile, target_user):
        try:
            worker_team_name = Team.objects.get(pk=profile.team_id).name
        except Team.DoesNotExist:
            worker_team_name = None

        context['worker_team_name'] = worker_team_name
        context['managed_teams'] = Team.get_teams_managed_by(target_user)

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
        context['chart_max'] = context['total_days']

    def _add_requests_context(self, context, target_user):
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
