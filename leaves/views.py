from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date
from leave_requests.display_vacations import vacations


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