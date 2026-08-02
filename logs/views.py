from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from logs.models import ChangeLog


@login_required
def log_history(request):
    logs = ChangeLog.objects.all().order_by('-created_at')
    return render(request, 'logs/log_history.html', {'logs': logs})


@login_required
def log_detail(request, pk):
    log = get_object_or_404(ChangeLog, pk=pk)
    return render(request, 'logs/log_detail.html', {'log': log})