from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import date
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from django.views.generic import  CreateView, UpdateView
from database.leave_requests_db import load_leave_requests, save_leave_requests
from django.contrib import messages
from accounts.permission import Permission
from logs.models import ChangeLog
from leaves.models import LeaveRequest
import csv
from django.http import HttpResponse
from .forms import LeaveRequestForm
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import View



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
    today = date.today()

    my_requests = LeaveRequest.objects.filter(employee=request.user)

    current = []
    planned = []
    archival = []

    for req in my_requests:
        entry = {
            'pk': req.pk,
            'start_date': req.start_date,
            'end_date': req.end_date,
            'days': req.amount_days,
            'status': req.status,
        }

        # 1. Każdy oczekujący wniosek traktujemy jako "Planowany" (niezależnie od daty)
        if req.status == LeaveRequest.Status.PENDING:
            planned.append(entry)

        # 2. Każdy odrzucony lub anulowany wniosek trafia od razu do historii
        elif req.status in [LeaveRequest.Status.CANCELED, LeaveRequest.Status.REJECTED]:
            archival.append(entry)

        # 3. Zatwierdzony urlop, który trwa właśnie DZISIAJ
        elif req.start_date <= today <= req.end_date and req.status == LeaveRequest.Status.APPROVED:
            current.append(entry)

        # 4. Zatwierdzony urlop, który odbędzie się w PRZYSZŁOŚCI (start_date > today)
        elif req.start_date > today and req.status == LeaveRequest.Status.APPROVED:
            planned.append(entry)

        # 5. Wszystko inne (stare, zatwierdzone urlopy, które już minęły)
        else:
            archival.append(entry)

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


class LeaveRequestView(LoginRequiredMixin, CreateView):
    """
     Widok odpowiedzialny za tworzenie nowego wniosku urlopowego.
     Wymaga zalogowania użytkownika.
    """
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'leaves/new_request.html'
    success_url = reverse_lazy('my_vacations')

    def get_form_kwargs(self):
        """
        Przekazuje zalogowanego użytkownika do formularza jako dodatkowy argument (kwargs),
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """
        Obsługuje proces po poprawnym wypełnieniu formularza.
         1. Jeśli wniosek nie został jeszcze potwierdzony w modalu (potwierdzenie dwuetapowe),
            przerywa zapis i zwraca widok z parametrem show_modal=True.
         2. Po ostatecznym potwierdzeniu, przypisuje wniosek do zalogowanego użytkownika i go zapisuje.
        """
        is_confirmed = form.cleaned_data.get('confirmed') == 'true'
        if not is_confirmed:
            # Użytkownik wysłał formularz po raz pierwszy, pokazujemy okno podsumowania (modal)
            context = self.get_context_data(form=form, show_modal=True)
            return self.render_to_response(context)

        # Użytkownik potwierdził wniosek w modalu, zapisujemy w bazie
        obj = form.save(commit=False)
        obj.employee = self.request.user
        obj.amount_days = form.cleaned_data['amount_days']
        obj.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """
        Rozbudowuje kontekst szablonu o dodatkowe dane:
         - Dostępną liczbę dni urlopowych pracownika.
         - Wyliczone dane z formularza (liczba dni, sformatowane daty), jeśli formularz jest poprawny.
        """
        from leaves.models import WorkerProfile
        context = super().get_context_data(**kwargs)
        form = context['form']

        # Pobieranie puli dostępnych dni urlopowych profilu pracownika
        try:
            profile = WorkerProfile.objects.get(user=self.request.user)
            context['available_days'] = profile.get_leave_days()
        except WorkerProfile.DoesNotExist:
            context['available_days'] = None

        # Formatowanie dat do wyświetlenia w podsumowaniu (modalu)
        if form.is_bound and form.is_valid():
            context['amount_days'] = form.cleaned_data.get('amount_days')
            context['start_date'] = form.cleaned_data.get('start_date').strftime('%d.%m.%Y')
            context['end_date'] = form.cleaned_data.get('end_date').strftime('%d.%m.%Y')
        else:
            context['amount_days'] = None
            context['start_date'] = None
            context['end_date'] = None

        return context

class LeaveRequestUpdateView(LoginRequiredMixin, UpdateView):
    """
    Widok odpowiedzialny za edycję istniejącego wniosku urlopowego.
    Zawiera walidację uprawnień oraz stanu wniosku.
    """
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'leaves/edit_request.html'
    success_url = reverse_lazy('my_vacations')

    def dispatch(self, request, *args, **kwargs):
        """
        Główna metoda kontrolująca dostęp do widoku. Sprawdza:
         1. Czy rola użytkownika pozwala ogólnie na modyfikację wniosków.
         2. Czy wniosek ma status "PENDING" (oczekujący) – tylko takie można edytować.
         3. Czy pracownik  próbuje edytować swój własny wniosek, a nie cudzy.
        """

        # Sprawdzenie uprawnień globalnych dla roli
        if not Permission.verifyPermission(request.user.role, 'can_change_request'):
            return redirect('dashboard')

        obj = self.get_object()

        # Blokada edycji wniosków, które zostały już zaakceptowane lub odrzucone
        if obj.status != LeaveRequest.Status.PENDING:
            messages.error(request, "Można edytować tylko wnioski oczekujące.")
            return redirect('my_vacations')

        # Pracownik nie może edytować wniosków innych osób
        if obj.employee != request.user:
            messages.error(request, "Możesz edytować tylko własne wnioski.")
            return redirect('my_vacations')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """
        Przekazuje zalogowanego użytkownika do formularza edycji.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """
        Obsługuje proces zapisu edytowanego wniosku.
        Podobnie jak przy tworzeniu – najpierw wymusza potwierdzenie w modalu (`confirmed == 'true'`).
        """
        is_confirmed = form.cleaned_data.get('confirmed') == 'true'
        if not is_confirmed:
            context = self.get_context_data(form=form, show_modal=True)
            return self.render_to_response(context)

        # Zapis zaktualizowanych danych wniosku
        obj = form.save(commit=False)
        obj.amount_days = form.cleaned_data['amount_days']
        obj.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """
        Rozbudowuje kontekst szablonu edycji. Oprócz aktualnie wprowadzanych danych i dostępnych dni,
        dorzuca do kontekstu pierwotne daty wniosku (`existing_start`, `existing_end`) przed edycją.
        """
        from leaves.models import WorkerProfile
        context = super().get_context_data(**kwargs)
        form = context['form']

        # Pobranie obecnych (starych) dat wniosku z bazy danych w celu wyświetlenia ich w szablonie
        pk = self.kwargs['pk']
        leave_request = LeaveRequest.objects.get(pk=pk)
        context['existing_start'] = leave_request.start_date.strftime('%d.%m.%Y')
        context['existing_end'] = leave_request.end_date.strftime('%d.%m.%Y')

        # Pobranie puli dostępnych dni urlopowych
        try:
            profile = WorkerProfile.objects.get(user=self.request.user)
            context['available_days'] = profile.get_leave_days()
        except WorkerProfile.DoesNotExist:
            context['available_days'] = None

        # Formatowanie nowo wpisywanych w formularzu dat
        if form.is_bound and form.is_valid():
            context['amount_days'] = form.cleaned_data.get('amount_days')
            context['start_date'] = form.cleaned_data.get('start_date').strftime('%d.%m.%Y')
            context['end_date'] = form.cleaned_data.get('end_date').strftime('%d.%m.%Y')
        else:
            context['amount_days'] = None
            context['start_date'] = None
            context['end_date'] = None

        return context

@method_decorator(require_POST, name='dispatch')
class CancelLeaveView(LoginRequiredMixin, View):

    def post(self, request, pk):
        leave_request = get_object_or_404(LeaveRequest, pk=pk)

        # sprawdź uprawnienie roli
        if not Permission.verifyPermission(request.user.role, 'can_cancel_request'):
            messages.error(request, "Nie masz uprawnień do anulowania wniosków.")
            return redirect('dashboard')

        # Worker tylko własne
        if request.user.role == 'Worker' and leave_request.employee != request.user:
            messages.error(request, "Możesz anulować tylko własne wnioski.")
            return redirect('my_vacations')

        # tylko pending
        if leave_request.status != LeaveRequest.Status.PENDING:
            messages.error(request, "Można anulować tylko wnioski oczekujące.")
            return redirect('my_vacations')

        leave_request.cancel_request(who=request.user)
        messages.success(request, "Wniosek został anulowany.")

        # Worker wraca do swoich, reszta do listy wszystkich
        if request.user.role == 'Worker':
            return redirect('my_vacations')
        return redirect('all_requests_list')

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
