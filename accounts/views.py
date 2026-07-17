from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from leaves.models import WorkerProfile
from .models import User
from .permission import Permission
from accounts.permission import role_required
from logs.models import AuthLog, ActivityLog
from logs.utils import get_client_ip
from django.contrib.auth import get_user_model
from accounts.forms import AddUserForm
from datetime import date

from django.conf import settings
from utils.email_utils import send_deactivation_email

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
    if new_role in ALLOWED_ROLES.get(request.user.role, []):
        old_role = request.session.get('active_role', request.user.role)
        request.session['active_role'] = new_role
        messages.success(request, "Rola została zmieniona poprawnie!")
        ActivityLog.objects.create(
            who=request.user,
            action='role_change',
            object_type='user',
            object_id=request.user.id,
            details=f"Zmieniono aktywną rolę z {old_role} na {new_role}",
        )
        return redirect('dashboard')
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
        return redirect('dashboard')

@login_required
@role_required("can_add_user")
def add_user(request):
    if request.method == 'POST':
        form = AddUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            team = form.cleaned_data.get('team')
            hire_date = form.cleaned_data.get('hire_date') or date.today()
            other_experience_years= form.cleaned_data.get('other_experience_years')
            other_experience_days = form.cleaned_data.get('other_experience_days')

            if team:
                WorkerProfile.objects.create(
                    user=user,
                    team=team,
                    hire_date=hire_date,
                    other_experience_days=other_experience_days,
                    other_experience_years=other_experience_years,
                )

            # Logowanie akcji
            ActivityLog.objects.create(
                who=request.user,
                action='new_account',
                object_type='user',
                object_id= user.id,
                details=f'Utworzono nowego użytkownika: {user.username}'
            )
            messages.success(request, f'Użytkownik {user.username} został pomyślnie dodany.')
            return redirect('user_list')
    else:
        form = AddUserForm()

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

            # Logowanie akcji
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

    User = get_user_model()
    users = User.objects.all()

    return render(request, 'accounts/reset_password.html', {'users': users})

