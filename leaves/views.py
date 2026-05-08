from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date


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

    today = date.today()

    # TODO: Tutaj trzeba załadować wnioski danego użytkownika
    # Na razie wstawiam mock data - później zmienimy na prawdziwe ładowanie z DB

    mock_vacations = [
        {
            'id': 1,
            'start_date': date(2026, 5, 5),
            'end_date': date(2026, 5, 15),
            'amount_days': 11,
            'type': 'Wypoczynkowy',
            'status': 'W trakcie',
        },
            {
            'id': 2,
            'start_date': date(2026, 6, 10),
            'end_date': date(2026, 6, 20),
            'amount_days': 11,
            'type': 'Wypoczynkowy',
            'status': 'Zatwierdzony',
        },
        {
            'id': 3,
            'start_date': date(2026, 3, 1),
            'end_date': date(2026, 3, 10),
            'amount_days': 10,
            'type': 'Wypoczynkowy',
            'status': 'Zatwierdzony',
        },
    ]

    current = []
    planned = []
    archival = []

    for req in mock_vacations:
        if req['start_date'] <= today <= req['end_date']:
            current.append(req)
        elif req['start_date'] > today:
            planned.append(req)
        else:
            archival.append(req)

    context = {
        'current_vacations': current,
        'planned_vacations': planned,
        'archival_vacations': archival,
    }

    return render(request, 'leaves/my_vacations.html', context)