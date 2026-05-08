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

    user = request.user
    today = date.today()

    my_vacation = [v for v in vacations if v['employee_id'] == user.id]

    # TODO: Tutaj trzeba załadować wnioski danego użytkownika
    # Na razie wstawiam mock data - później zmienimy na prawdziwe ładowanie z DB

    current = []
    planned = []
    archival = []

    for vacation in my_vacation:
        if vacation['start_date'] <= today <= vacation['end_date']:
            current.append(vacation)
        elif vacation['start_date'] > today:
            planned.append(vacation)
        else:
            archival.append(vacation)

    context = {
        'current_vacations': current,
        'planned_vacations': planned,
        'archival_vacations': archival,
        'user': user,
    }

    return render(request, 'leaves/my_vacations.html', context)