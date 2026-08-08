from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from logs.models import ChangeLog
from django.core.paginator import Paginator


@login_required
def log_history(request):
    logs = ChangeLog.objects.all().order_by('-created_at')

    # Filtry
    action = request.GET.get('action')
    severity = request.GET.get('severity')
    username = request.GET.get('username')

    if action:
        logs = logs.filter(action=action)
    if severity:
        logs = logs.filter(severity=severity)
    if username:
        logs = logs.filter(who__username__icontains=username)

    # Paginacja
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'logs/log_history.html', {
        'page_obj': page_obj,
        'action_choices': ChangeLog.ACTION_CHOICES,
        'severity_choices': ChangeLog.SEVERITY_CHOICES,
    })

@login_required
def log_detail(request, pk):
    log = get_object_or_404(ChangeLog, pk=pk)
    return render(request, 'logs/log_detail.html', {'log': log})