from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import User
from permission import role_required

@login_required
@role_required('can_view_user_list')
def user_list(request):
    users = User.objects.all()
    return render(request, 'accounts/user_list.html', {'users': users})


