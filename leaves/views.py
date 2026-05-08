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

    # Pobieramy tylko wnioski użytkownika
    my_vacation = [v for v in vacations if v['employee_id'] == request.user.id]

    current = []
    planned = []
    archival = []

    for v in my_vacation:
        days = (v['end_date'] - v['start_date']).days + 1

        vacation = v.copy()
        vacation['days'] = days

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