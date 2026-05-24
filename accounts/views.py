from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import User
from .permission import Permission
from permission import role_required


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
    users = User.objects.all()
    return render(request, 'accounts/user_list.html', {'users': users})


