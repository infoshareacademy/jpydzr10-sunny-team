from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date
from leave_requests.leave_request import LeaveRequest
from database.database import load_users


@login_required(login_url='/accounts/login/')
def dashboard(request):
    context = {
        'title': 'Dashboard Urlopowy',
    }
    return render(request, 'leaves/dashboard.html', context)

@login_required
def all_requests_list(request):
    return render(request, 'leaves/all_requests_list.html')

@login_required
def my_vacations(request):
    user = request.user
    today = date.today()

    users = load_users()

    # TODO: Tutaj trzeba załadować wnioski danego użytkownika
    # Na razie wstawiam mock data - później zmienimy na prawdziwe ładowanie z DB

    mock_requests = [
        LeaveRequest(employee_id=user.id, first_name=user.first_name, last_name=user.last_name,
                     start_date=date(2026, 5,  5), end_date=date(2026, 5, 15),
                     amount_days=11),
        LeaveRequest(employee_id=user.id, first_name=user.first_name, last_name=user.last_name,
                     start_date=date(2026, 6, 10), end_date=date(2026, 6, 20),
                     amount_days=11),
        LeaveRequest(employee_id=user.id, first_name=user.first_name, last_name=user.last_name,
                     start_date=date(2026, 3, 1), end_date=date(2026, 3, 10),
                     amount_days=10),
    ]

    current = []
    planned = []
    archival = []

    for req in mock_requests:
        if req.start_date <= today <= request.end_date:
            current.append(request)
        elif req.start_date > today:
            planned.append(request)
        else:
            archival.append(request)

    context = {
        'current_vacations': current,
        'planned_vacations': planned,
        'archival_vacations': archival,
        'user': user,
    }

    return render(request, 'leaves/my_vacations.html', context)