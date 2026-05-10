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


@login_required(login_url='/accounts/login/')
def dashboard(request):
    context = {
        'title': 'Dashboard Urlopowy',
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
            'created_at': getattr(req, 'created_at', None)
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
        user_role = "Admin"

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
        user_role = "Admin"

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

