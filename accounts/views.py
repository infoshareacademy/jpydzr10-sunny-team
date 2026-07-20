from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView

from leaves.models import WorkerProfile, LeaveRequest
from .models import User
from .permission import Permission
from accounts.permission import role_required
from logs.models import AuthLog, ActivityLog
from logs.utils import get_client_ip
from django.contrib.auth import get_user_model
from accounts.forms import AddUserForm
from datetime import date

from django.conf import settings
from mail.utils import send_deactivation_email

@login_required
def deactivate_user(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if target_user.role in ('HR', 'Manager'):
        required_action = 'can_deactivate_staff'
    else:
        required_action = 'can_deactivate_worker'
    if not Permission.verifyPermission(request.user.role, required_action):
        messages.error(request, 'Nie masz uprawnień do dezaktywacji tego konta')
        return redirect('dashboard')
    if request.method == 'POST':
        target_user.is_active = False
        target_user.save()
        return redirect('user_list')

    # --- WYŚLIJ MAIL O DEZAKTYWACJI ---
    if target_user.email:
        send_deactivation_email(
            user_email=target_user.email,
            user_name=f"{target_user.first_name} {target_user.last_name}",
            site_url=settings.SITE_URL,
        )

    return render(request, 'accounts/deactivate_user.html', {'target_user': target_user})


@login_required
@role_required('can_view_user_list')
def user_list(request):
    from django.db.models import Case, When, IntegerField
    role_order = Case(
        When(role='Admin', then=0),
        When(role='Manager', then=1),
        When(role='HR', then=2),
        When(role='Worker', then=3),
        default=4,
        output_field=IntegerField(),
    )
    users = User.objects.exclude(role='Admin').exclude(is_superuser=True).annotate(role_order=role_order).order_by(
        '-is_active', 'role_order', 'last_name', 'first_name'
    )
    return render(request, 'accounts/user_list.html', {'users': users})

@login_required
def switch_role(request):
    from accounts.context_processors import ALLOWED_ROLES
    new_role = request.POST.get("role")
    old_role = request.session.get('active_role', request.user.role)
    if new_role in ALLOWED_ROLES.get(request.user.role, []):
        request.session['active_role'] = new_role
        messages.success(request, f"Zmieniono aktywną rolę z {old_role} na {new_role}.")
        ActivityLog.objects.create(
            who=request.user,
            action='role_change',
            object_type='user',
            object_id=request.user.id,
            details=f"Zmieniono aktywną rolę z {old_role} na {new_role}.",
        )
        return redirect('home')

    elif  new_role == old_role:
        messages.info(request, f"Jesteś już w roli: {new_role}")
        return redirect('home')

    else:
        messages.error(request, 'Nie masz uprawnień do tej roli')
        AuthLog.objects.create(
            user=request.user,
            username=request.user.username,
            action='access_denied_403',
            severity='warning',
            details=f"Proba zmiany roli na: {new_role}",
            ip_address=get_client_ip(request),
        )
        return redirect('home')

@login_required
@role_required("can_add_user")
def add_user(request):
    ROLE_ASSIGNMENT_PERMISSIONS = {
        'Admin': ['Worker', 'Manager', 'HR', 'Admin'],
        'HR': ['Worker', 'Manager'],
    }
    active_role = request.session.get('active_role', request.user.role)
    allowed_roles = ROLE_ASSIGNMENT_PERMISSIONS.get(active_role, [])

    if request.method == 'POST':
        form = AddUserForm(request.POST, allowed_roles=allowed_roles)
        if form.is_valid():
            user = form.save()
            team = form.cleaned_data.get('team')
            hire_date = form.cleaned_data.get('hire_date') or date.today()
            other_experience_years = form.cleaned_data.get('other_experience_years')
            other_experience_days = form.cleaned_data.get('other_experience_days')
            if team:
                WorkerProfile.objects.create(
                    user=user,
                    team=team,
                    hire_date=hire_date,
                    other_experience_days=other_experience_days,
                    other_experience_years=other_experience_years,
                )
            ActivityLog.objects.create(
                who=request.user,
                action='new_account',
                object_type='user',
                object_id=user.id,
                details=f'Utworzono nowego użytkownika: {user.username}'
            )
            messages.success(request, f'Użytkownik {user.username} został pomyślnie dodany.')
            return redirect('user_list')
        else:
            if 'role' in form.errors:
                AuthLog.objects.create(
                    user=request.user,
                    username=None,
                    action='access_denied_403',
                    details=f"Próba nadania niedozwolonej roli. Aktywna rola: {active_role}",
                    ip_address=get_client_ip(request),
                    severity='warning',
                )
    else:
        form = AddUserForm(allowed_roles=allowed_roles)

    return render(request, 'accounts/add_user.html', {'form': form})

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
                messages.error(request, 'Hasło musi mieć conajmniej 6 znaków.')
                return redirect('reset_password')

            user.set_password(new_password)
            user.save()

            ActivityLog.objects.create(
                who=request.user,
                action='password_reset',
                object_type='user',
                object_id= user_id,
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


class ProfileView(LoginRequiredMixin, DetailView):
    model = WorkerProfile
    template_name = 'accounts/profile.html'
    context_object_name = 'profile'

    def get(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')
        target_user = get_object_or_404(User, pk=user_id) if user_id else request.user
        active_role = request.session.get('active_role', request.user.role)
        position = target_user.role

        if not self._has_access(request.user, target_user, active_role):
            AuthLog.objects.create(
                user=request.user,
                username=None,
                action='access_denied_403',
                details=f"Próba podglądu profilu {target_user.username} (id={target_user.id}). Aktywna rola: {active_role}",
                ip_address=get_client_ip(request),
                severity='warning',
            )
            messages.info(request, 'Nie masz uprawnień do przeglądania tego profilu')
            return redirect('home')

        self.object = get_object_or_404(WorkerProfile, user=target_user)
        context = self.get_context_data(object=self.object, target_user=target_user, active_role=active_role, position=position)
        return self.render_to_response(context)

    def _has_access(self, viewer, target_user, active_role):
        if target_user == viewer:
            return True
        if active_role == 'Admin':
            return True
        if active_role == 'HR':
            return target_user.role not in ['HR', 'Admin']
        if active_role == 'Manager':
            try:
                return target_user.role == "Worker" and viewer.worker_profile.team == target_user.worker_profile.team
            except WorkerProfile.DoesNotExist:
                return False
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_user = kwargs['target_user']
        active_role = kwargs['active_role']
        profile = self.object
        position = kwargs['position']

        context['profile_owner'] = target_user
        context['is_own_profile'] = (self.request.user == target_user)
        context['is_admin'] = active_role == 'Admin'
        context['active_role'] = active_role

        try:
            total_days = profile._get_total_leave_days()
            used_days = profile.used_leave_days
            remaining_days = profile.get_leave_days()
            progress_percent = round((used_days / total_days) * 100) if total_days > 0 else 0
        except WorkerProfile.DoesNotExist:
            total_days = used_days = remaining_days = None
            progress_percent = 0

        today = date.today()
        current_year = today.year

        start_month = 1 if profile.hire_date.year < current_year else profile.hire_date.month

        finished_leaves = LeaveRequest.objects.filter(
            employee=target_user,
            status=LeaveRequest.Status.APPROVED,
            start_date__year=current_year,
            end_date__lt=today,
        )

        monthly_used = [0] * (today.month - start_month + 1)
        for leave in finished_leaves:
            idx = leave.start_date.month - start_month
            if 0 <= idx < len(monthly_used):
                monthly_used[idx] += leave.amount_days

        cumulative = []
        running = 0
        for v in monthly_used:
            running += v
            cumulative.append(running)

        context['total_days'] = total_days
        context['used_days'] = used_days
        context['current_year'] = current_year
        context['remaining_days'] = remaining_days
        context['progress_percent'] = progress_percent

        month_names = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru']
        context['chart_labels'] = month_names[start_month - 1:today.month]
        context['chart_values'] = cumulative
        context['chart_max'] = context['total_days']

        target_requests = LeaveRequest.objects.filter(
            employee=target_user,
            end_date__gte=date.today()
        ).filter(
            Q(status='approved') | Q(status='pending')
        )

        has_access_to_activity = (
                context['is_own_profile'] or
                active_role in ['Admin', 'HR', 'Manager']
        )

        if has_access_to_activity:
            context['activity_logs'] = ActivityLog.objects.filter(
                who=target_user,
                object_type='leave_request',
            ).order_by('-created_at')[:6]
        else:
            context['activity_logs'] = []

        context['recent_requests'] = target_requests.order_by('-created_at')[:5]
        context['active_count'] = target_requests.exclude(status=LeaveRequest.Status.CANCELED).count()
        context['pending_count'] = target_requests.filter(status=LeaveRequest.Status.PENDING).count()
        context['position']=position

        return context
