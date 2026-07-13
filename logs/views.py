from datetime import datetime, time
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone as dj_timezone

from accounts.permission import role_required
from logs.models import ActivityLog, AuthLog

User = get_user_model()


@login_required
@role_required("can_view_logs")
def activity_log_history(request):
    logs = ActivityLog.objects.all().order_by("-created_at")

    # Pobieranie filtrów
    action_filter = request.GET.get("action", "")
    object_type_filter = request.GET.get("object_type", "")
    user_filter = request.GET.get("user", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    # Aplikowanie filtrów
    if action_filter:
        logs = logs.filter(action=action_filter)

    if object_type_filter:
        logs = logs.filter(object_type=object_type_filter)

    if user_filter:
        try:
            logs = logs.filter(who_id=int(user_filter))
        except ValueError:
            pass

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
            start = dj_timezone.make_aware(
                datetime.combine(date_from_obj, time.min)
            )
            logs = logs.filter(created_at__gte=start)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
            end = dj_timezone.make_aware(
                datetime.combine(date_to_obj, time.max)
            )
            logs = logs.filter(created_at__lte=end)
        except ValueError:
            pass

    # Paginacja
    paginator = Paginator(logs, 20)
    page_number = request.GET.get("page")
    logs_page = paginator.get_page(page_number)

    users = User.objects.all().order_by("username")

    context = {
        "logs": logs_page,
        "action_filter": action_filter,
        "object_type_filter": object_type_filter,
        "user_filter": user_filter,
        "date_from": date_from,
        "date_to": date_to,
        "action_choices": ActivityLog.ACTION_CHOICES,
        "severity_choices": ActivityLog.SEVERITY_CHOICES,
        "object_type_choices": ActivityLog.OBJECT_TYPE_CHOICES,
        "users": users,
    }

    return render(request, "logs/activity_log.html", context)


@login_required
@role_required("can_view_logs")
def auth_log_history(request):
    logs = AuthLog.objects.select_related("user").order_by("-timestamp")

    # Pobieranie filtrów
    action_filter = request.GET.get("action", "")
    severity_filter = request.GET.get("severity", "")
    user_filter = request.GET.get("user", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    # Aplikowanie filtrów
    if action_filter:
        logs = logs.filter(action=action_filter)

    if severity_filter:
        logs = logs.filter(severity=severity_filter)

    if user_filter:
        try:
            logs = logs.filter(user_id=int(user_filter))
        except ValueError:
            pass

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
            start = dj_timezone.make_aware(
                datetime.combine(date_from_obj, time.min)
            )
            logs = logs.filter(timestamp__gte=start)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
            end = dj_timezone.make_aware(
                datetime.combine(date_to_obj, time.max)
            )
            logs = logs.filter(timestamp__lte=end)
        except ValueError:
            pass

    # Paginacja
    paginator = Paginator(logs, 20)
    page_number = request.GET.get("page")
    logs_page = paginator.get_page(page_number)

    users = User.objects.all().order_by("username")

    context = {
        "logs": logs_page,
        "action_filter": action_filter,
        "severity_filter": severity_filter,
        "user_filter": user_filter,
        "date_from": date_from,
        "date_to": date_to,
        "action_choices": AuthLog.ACTION_CHOICES,
        "severity_choices": AuthLog.SEVERITY_CHOICES,
        "users": users,
    }
    return render(request, "logs/auth_log.html", context)