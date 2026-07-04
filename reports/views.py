from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from accounts.models import User
from django.http import HttpResponse
from leaves.models import WorkerProfile
import csv

def reports_index(request):
    return render(request, 'reports/index.html')


@login_required
def users_per_role_report(request):
    active_role = request.session.get('active_role', request.user.role)

    if active_role not in ['Admin', 'Manager', 'HR']:
        return render(request, 'leaves/access_denied.html')

    role_stats = (
        User.objects
        .values('role')
        .annotate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
        )
        .order_by('role')
    )

    report_rows = []
    for row in role_stats:
        total = row['total']
        active = row['active']
        percent_active = round(active / total * 100, 1) if total else 0
        report_rows.append({
            'role': row['role'] or 'Brak roli',
            'total': total,
            'active': active,
            'percent_active': percent_active,
        })

    context = {
        'report_rows': report_rows,
    }
    return render(request, 'reports/users_per_role.html', context)


def _leave_usage_profiles(request, active_role):
    """
    Zwraca profile pracowników widoczne dla danej roli.
    Manager widzi tylko swój zespół (tak samo jak team_leave_balance
    i export_requests_csv w leaves/views.py), HR i Admin widzą wszystkich.
    """
    profiles = WorkerProfile.objects.select_related('user').order_by('team', 'user__last_name')

    if active_role == 'Manager':
        try:
            my_profile = WorkerProfile.objects.get(user=request.user)
            profiles = profiles.filter(team=my_profile.team)
        except WorkerProfile.DoesNotExist:
            profiles = profiles.none()

    return profiles


def _leave_usage_rows(profiles):
    """Liczy przydzielone/wykorzystane/pozostałe dni i % wykorzystania dla każdego profilu."""
    rows = []
    for profile in profiles:
        total = profile._get_total_leave_days()
        used = profile.used_leave_days
        remaining = profile.get_leave_days()
        percent_used = round(used / total * 100, 1) if total else 0
        rows.append({
            'first_name': profile.user.first_name,
            'last_name': profile.user.last_name,
            'team': profile.team,
            'total': total,
            'used': used,
            'remaining': remaining,
            'percent_used': percent_used,
        })
    return rows


@login_required
def leave_usage_report(request):
    active_role = request.session.get('active_role', request.user.role)

    if active_role not in ['Admin', 'Manager', 'HR']:
        return render(request, 'leaves/access_denied.html')

    profiles = _leave_usage_profiles(request, active_role)
    report_rows = _leave_usage_rows(profiles)

    context = {
        'report_rows': report_rows,
    }
    return render(request, 'reports/leave_usage.html', context)


@login_required
def export_leave_usage_csv(request):
    """
    Eksport CSV raportu wykorzystania urlopów per użytkownik.
    Zbudowane na wzór leaves.views.export_requests_csv (te same reguły
    dostępu i widoczności zespołu Managera), ale dla innego zestawu danych.
    """
    active_role = request.session.get('active_role', request.user.role)

    if active_role not in ['Admin', 'Manager', 'HR']:
        return render(request, 'leaves/access_denied.html')

    profiles = _leave_usage_profiles(request, active_role)
    report_rows = _leave_usage_rows(profiles)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="wykorzystanie_urlopow.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Imię', 'Nazwisko', 'Zespół',
        'Przydzielone dni', 'Wykorzystane dni', 'Pozostałe dni', '% wykorzystania',
    ])

    for row in report_rows:
        writer.writerow([
            row['first_name'],
            row['last_name'],
            row['team'],
            row['total'],
            row['used'],
            row['remaining'],
            row['percent_used'],
        ])

    return response