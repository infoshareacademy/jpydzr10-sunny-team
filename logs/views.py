from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from datetime import datetime, time
from accounts.permission import role_required
from logs.models import ActivityLog, AuthLog


@login_required
@role_required("can_view_logs")
def activity_log_history(request):

    logs = ActivityLog.objects.all().order_by('-created_at')

    # Filtry
    action_filter = request.GET.get('action', '')
    object_type_filter = request.GET.get('object_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if action_filter:
        logs = logs.filter(action=action_filter)

    if object_type_filter:
        logs = logs.filter(object_type=object_type_filter)

    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)

    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)

    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    logs = paginator.get_page(page_number)

    context = {
        'logs': logs,
        'action_filter': action_filter,
        'object_type_filter': object_type_filter,
        'date_from': date_from,
        'date_to': date_to,
        'action_choices': ActivityLog.ACTION_CHOICES,
        'severity_choices': ActivityLog.SEVERITY_CHOICES,
    }

    return render(request, 'logs/activity_log.html', context)

@login_required
@role_required("can_view_logs")
def auth_log_history(request):
    logs = AuthLog.objects.select_related('user').order_by('-timestamp')

    action_filter = request.GET.get('action', '')
    severity_filter = request.GET.get('severity', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if action_filter:
        logs = logs.filter(action=action_filter)
    if severity_filter:
        logs = logs.filter(severity=severity_filter)
    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        logs = logs.filter(timestamp__gte=datetime.combine(date_from_obj, time.min))
    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        logs = logs.filter(timestamp__lte=datetime.combine(date_to_obj, time.max))

    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    logs = paginator.get_page(page_number)


    context = {
        'logs': logs,
        'action_filter': action_filter,
        'date_from': date_from,
        'date_to': date_to,
        'action_choices': AuthLog.ACTION_CHOICES,
        'severity_choices': AuthLog.SEVERITY_CHOICES,
    }
    return render(request, 'logs/auth_log.html', context)

