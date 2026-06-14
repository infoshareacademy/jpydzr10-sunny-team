from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import User
from .permission import Permission
from accounts.permission import role_required


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
    ALLOWED_ROLES = {
        'Manager': ['Manager', 'Worker'],
        'HR': ['HR', 'Worker'],
        'Admin': ['Admin'],
        'Worker': ['Worker'],
    }
    new_role = request.POST.get("role")
    if new_role in ALLOWED_ROLES.get(request.user.role, []):
        request.session['active_role'] = new_role
        messages.success(request,"Rola została zmieniona poprawnie!")
        return redirect('dashboard')
    else:
        messages.error(request, 'Nie masz uprawnień do tej roli')
        return redirect('dashboard')

