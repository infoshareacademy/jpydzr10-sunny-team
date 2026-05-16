from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import User
from .permission import Permission


@login_required
def deactivate_user(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if target_user.role in ('HR', 'Manager'):
        required_action = 'can_deactivate_staff'
    else:
        required_action = 'can_deactivate_worker'

    if not Permission.verifyPermission(request.user.role, required_action):
        return redirect('dashboard')

    if request.method == 'POST':
        target_user.is_active = False
        target_user.save()
        return redirect('user_list')

    return render(request, 'accounts/deactivate_user.html', {'target_user': target_user})