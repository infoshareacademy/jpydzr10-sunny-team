from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from datetime import date
from django.views.decorators.http import require_POST
from leave_requests.display_vacations import vacations
from database.leave_requests_db import load_leave_requests, save_leave_requests
from django.http import JsonResponse
from .services import count_leave_days_service
from django.contrib import messages
from accounts.permission import Permission
from logs.models import ChangeLog
from leaves.models import WorkerProfile, LeaveRequest
import csv
from django.http import HttpResponse
import calendar
from datetime import timedelta


@login_required
def dashboard(request):
    from leaves.models import WorkerProfile

    try:
        profile = WorkerProfile.objects.get(user=request.user)
        total_days = profile._get_total_leave_days()
        used_days = profile.used_leave_days
        remaining_days = profile.get_leave_days()
        # pasek postępu: ile % urlopu wykorzystano (0-100)
        progress_percent = round((used_days / total_days) * 100) if total_days > 0 else 0
    except WorkerProfile.DoesNotExist:
        # jeśli zalogowany user nie ma profilu (np. Admin bez profilu)
        total_days = None
        used_days = None
        remaining_days = None
        progress_percent = 0

    my_requests = LeaveRequest.objects.filter(employee=request.user)
    active_count = my_requests.exclude(status=LeaveRequest.Status.CANCELED).count()
    pending_count = my_requests.filter(status=LeaveRequest.Status.PENDING).count()

    context = {
        'title': 'Dashboard Urlopowy',
        'total_days': total_days,
        'used_days': used_days,
        'remaining_days': remaining_days,
        'progress_percent': progress_percent,
        'active_count': active_count,
        'pending_count': pending_count,
    }

    return render(request, 'leaves/dashboard.html', context)

@login_required
def all_requests_list(request):

    status_filter = request.GET.get('status', '').lower()

    # Ładujemy wnioski z bazy (tak jak w startup_app.py)
    leave_requests = load_leave_requests()

    all_vacations = []

    for req_id, req in leave_requests.items():
        days = (req.end_date - req.start_date).days + 1

        vacation = {
            'id': req_id,
            'employee_id': req.employee_id,
            'first_name': req.first_name,
            'last_name': req.last_name,
            'start_date': req.start_date,
            'end_date': req.end_date,
            'days': days,
            'status': req.status.value if hasattr(req.status, 'value') else req.status,
            'who_confirmed': req.who_confirmed,
            'created_at': getattr(req, 'created_at', None) # Narazie nie pobiera nic bo pobiera dane z pliku csv, który
                                                           # nie zapisuje nawet takiej informacji
        }
        all_vacations.append(vacation)

    # Filtr statusu
    if status_filter:
        all_vacations = [v for v in all_vacations if v['status'].lower() == status_filter]

    context = {
        'all_vacations': all_vacations,
        'status_filter': status_filter,
    }

    return render(request, 'leaves/all_requests_list.html', context)

@login_required
def my_vacations(request):

    # Zduplikowana logika z leave_requests/display_vacations.py
    # Trzeba to potem zrefactorować gdy będziemy pobierali dane z DB
    today = date.today()

    # Pobieramy tylko wnioski użytkownika
    my_vacation = [v for v in vacations if v['employee_id'] == request.user.id]

    current = []
    planned = []
    archival = []

    for v in my_vacation:
        days = (v['end_date'] - v['start_date']).days + 1

        vacation = v.copy()
        vacation['days'] = days

        if v['start_date'] <= today <= v['end_date']:
            current.append(vacation)
        elif v['start_date'] > today:
            planned.append(vacation)
        else:
            # Filtrujemy archiwalne wnioski tak by nie wyświetlały statusu oczekującego
            if v['status'] != 'pending':
                archival.append(vacation)

    context = {
        'current_vacations': current,
        'planned_vacations': planned,
        'archival_vacations': archival,
    }

    return render(request, 'leaves/my_vacations.html', context)

@login_required
@require_POST
def approve_request(request, request_id):

    leave_requests = load_leave_requests()

    if request_id not in leave_requests:
        messages.error(request, 'Nie znaleziono wniosku')
        return redirect('all_requests_list')

    req = leave_requests[request_id]

    """Sprawdzamy czy użytkownik ma uprawnienia do akceptacji wniosku"""
    user_role = getattr(request.user, 'role', None)
    if not user_role:
        user_role = "Admin" # Tymczasowo, bo nie ma loginu utworzonego i logujemy sie jako admin

    if not Permission.verifyPermission(user_role, 'can_approve_request'):
        messages.error(request, 'Nie masz uprawnień do zatwierdzania wniosków urlopowych.')
        return redirect('all_requests_list')

    try:
        req.approve(who_confirmed=request.user.username)
        save_leave_requests(leave_requests)
        messages.success(request, f'Wniosek od {req.first_name} {req.last_name} został zatwierdzony.')
    except Exception as e:
        messages.error(request, f'Błąd podczas zatwierdzania: {e}')

    return redirect('all_requests_list')

@login_required
@require_POST
def reject_request(request, request_id):
    leave_requests = load_leave_requests()

    if request_id not in leave_requests:
        messages.error(request, 'Nie znaleziono wniosku')
        return redirect('all_requests_list')

    req = leave_requests[request_id]

    """Sprawdzamy czy użytkownik ma uprawnienia do odrzucania wniosku"""
    user_role = getattr(request.user, 'role', None)
    if not user_role:
        user_role = "Admin" # Tymczasowo, bo nie ma loginu utworzonego i logujemy sie jako admin

    if not Permission.verifyPermission(user_role, 'can_reject_request'):
        messages.error(request, 'Nie masz uprawnień do odrzucania wniosków urlopowych.')
        return redirect('all_requests_list')

    try:
        req.rejected(who_confirmed=request.user.username)
        save_leave_requests(leave_requests)
        messages.success(request, f'Wniosek od {req.first_name} {req.last_name} został odrzucony.')
    except Exception as e:
        messages.error(request, f'Błąd podczas odrzucania {e}')

    return redirect('all_requests_list')

@login_required
def new_request(request):
    return render(request, 'leaves/new_request.html')

@login_required
def calculate_days_api(request):
    try:
        count = count_leave_days_service(
            request.GET.get('start'),
            request.GET.get('end')
        )
        return JsonResponse({'count': count})
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def log_history(request):

    logs = ChangeLog.objects.all().order_by('-created_at')

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

    context = {
        'logs': logs,
        'action_filter': action_filter,
        'object_type_filter': object_type_filter,
        'date_from': date_from,
        'date_to': date_to,
    }

    return render(request, 'leaves/log_history.html', context)
@login_required
def team_leave_balance(request):
    # Tylko Manager i HR mają dostęp
    if request.user.role not in ['Manager', 'HR']:
        return render(request, 'leaves/access_denied.html')

    from leaves.models import WorkerProfile

    # Pobierz team managera/HR z jego własnego profilu
    try:
        my_profile = WorkerProfile.objects.get(user=request.user)
        team_name = my_profile.team
    except WorkerProfile.DoesNotExist:
        team_name = None

    # Pobierz wszystkich pracowników z tego samego zespołu
    if team_name:
        team_profiles = WorkerProfile.objects.filter(team=team_name).select_related('user')
    else:
        team_profiles = []

    team_data = []
    for profile in team_profiles:
        team_data.append({
            'first_name': profile.user.first_name,
            'last_name': profile.user.last_name,
            'total_days': profile._get_total_leave_days(),
            'used_days': profile.used_leave_days,
            'remaining_days': profile.get_leave_days(),
        })

    context = {
        'team_name': team_name,
        'team_data': team_data,
    }
    return render(request, 'leaves/team_leave_balance.html', context)


@login_required
def export_requests_csv(request):
    # tylko Manager i HR mają dostęp
    if request.user.role not in ['Manager', 'HR', 'Admin']:
        return render(request, 'leaves/access_denied.html')

    from leaves.models import LeaveRequest

    # odpowiedź HTTP jako plik CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="wnioski_urlopowe.csv"'

    writer = csv.writer(response)

    # nagłówki kolumn
    writer.writerow([
        'ID', 'Pracownik', 'Data od', 'Data do',
        'Dni', 'Status', 'Potwierdził', 'Data złożenia'
    ])

    # dane z bazy
    requests = LeaveRequest.objects.select_related('employee', 'who_confirmed').all()
    for req in requests:
        writer.writerow([
            req.id,
            f"{req.employee.first_name} {req.employee.last_name}",
            req.start_date,
            req.end_date,
            req.amount_days,
            req.get_status_display(),
            f"{req.who_confirmed.first_name} {req.who_confirmed.last_name}" if req.who_confirmed else '',
            req.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response


@login_required
def team_calendar(request):
    # miesięczny kalendarz urlopów dla całego zespołu

    if request.user.role not in ['Manager', 'HR']:
        return render(request, 'leaves/access_denied.html')

    # jeśli w url jest rok/mc to pobieram
    # jeśli brak to bieżący
    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    # dane którego zespołu
    try:
        my_profile = WorkerProfile.objects.get(user=request.user)
        team_name = my_profile.team
    except WorkerProfile.DoesNotExist:
        team_name = None

    # lista pracowników
    if team_name:
        team_profiles = (
            WorkerProfile.objects
            .filter(team=team_name)
            .select_related('user')
        )
    else:
        team_profiles = WorkerProfile.objects.none()

    team_members = [
        {
            'id': p.user.id,
            'name': f"{p.user.last_name} {p.user.first_name}",
        }
        for p in team_profiles
    ]

    # urlopy w statusie approved
    first_day = date(year, month, 1)    # 1. dzień mc-a
    last_day = date(year, month, calendar.monthrange(year, month)[1])   # ost. dzień mc-a

    team_user_ids = [m['id'] for m in team_members]

    approved_leaves = LeaveRequest.objects.filter(
        employee__id__in=team_user_ids,  # tylko ten zespół
        status=LeaveRequest.Status.APPROVED,
        start_date__lte=last_day,  # zaczyna się przed końcem miesiąca
        end_date__gte=first_day,  # kończy się po początku miesiąca
    ).select_related('employee')

    # słownik urlopowiczów z danego mc-a
    leave_map = {}

    for leave in approved_leaves:
        current = max(leave.start_date, first_day)
        end = min(leave.end_date, last_day)

        while current <= end:
            day_num = current.day

            if day_num not in leave_map:
                leave_map[day_num] = []

            name = f"{leave.employee.last_name} {leave.employee.first_name}"
            if name not in leave_map[day_num]:
                leave_map[day_num].append(name)

            current += timedelta(days=1)

    # miesięczny widok kalendarze
    # monthcalendar(rok, miesiąc) zwraca listę tygodni,
    # każdy tydzień to lista 7 liczb (0 = ten dzień należy do innego miesiąca)
    # Przykład: [[0, 0, 1, 2, 3, 4, 5], [6, 7, 8, ...], ...]
    cal = calendar.monthcalendar(year, month)

    # zamieniam siatkę liczbową na siatkę słowników z datą i urlopami
    weeks = []
    for week in cal:
        week_row = []
        for day_num in week:
            if day_num == 0:
                # dzień spoza miesiąca — pusta komórka
                week_row.append({'day': 0, 'leaves': [], 'is_today': False})
            else:
                week_row.append({
                    'day': day_num,
                    'leaves': leave_map.get(day_num, []),  # [] jeśli brak urlopów
                    'is_today': date(year, month, day_num) == today,
                })
        weeks.append(week_row)

    # poprzedni i następny miesiąc (do przycisków nawigacji)
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # do html
    context = {
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'weeks': weeks,
        'team_name': team_name,
        'team_members': team_members,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'today': today,
    }
    return render(request, 'leaves/team_calendar.html', context)