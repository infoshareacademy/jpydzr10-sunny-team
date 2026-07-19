from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime, date, timedelta
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView, View
from accounts.permission import Permission, role_required, RoleRequiredMixin
from leaves.models import LeaveRequest, WorkerProfile
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView
import csv
import calendar
from logs.models import AuthLog, ActivityLog
from logs.utils import get_client_ip
from .forms import LeaveRequestForm
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from .utils import Calendar_utils


@login_required
@role_required("can_see_all_requests")
def all_requests_list(request):
    status_filter = request.GET.get('status', '').lower()
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    active_role = request.session.get('active_role', request.user.role)

    qs = LeaveRequest.objects.select_related('employee', 'who_confirmed').all()

    # Manager widzi tylko swój zespół
    if active_role == 'Manager':
        try:
            my_profile = WorkerProfile.objects.get(user=request.user)
            team_members = WorkerProfile.objects.filter(team=my_profile.team).values_list('user', flat=True)
            qs = qs.filter(employee__in=team_members)
        except WorkerProfile.DoesNotExist:
            qs = qs.none()

    if status_filter and status_filter in LeaveRequest.Status.values:
        qs = qs.filter(status=status_filter)

    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            qs = qs.filter(end_date__gte=date_from)
        except ValueError:
            pass

    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            qs = qs.filter(start_date__lte=date_to)
        except ValueError:
            pass

    if active_role == 'HR':
        all_team_names = (
            WorkerProfile.objects
            .values_list('team', flat=True)
            .distinct()
            .order_by('team')
        )
        teams = []
        for team_name in all_team_names:
            teams.append({
                'team_name': team_name,
                'requests': qs.filter(employee__worker_profile__team=team_name),
            })
        context = {
            'teams': teams,
            'is_hr': True,
            'status_filter': status_filter,
            'date_from': date_from_str,
            'date_to': date_to_str,
        }
    else:
        context = {
            'all_vacations': qs,
            'status_filter': status_filter,
            'date_from': date_from_str,
            'date_to': date_to_str,
        }

    return render(request, 'leaves/all_requests_list.html', context)

@login_required
@role_required("can_see_own_requests")
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
@role_required("can_approve_request")
@require_POST
def approve_request(request, request_id):
    leave_request = get_object_or_404(LeaveRequest, pk=request_id)
    active_role = request.session.get('active_role', request.user.role)

    # Pobierz zespół pracownika składającego wniosek
    try:
        employee_profile = WorkerProfile.objects.get(user=leave_request.employee)
        employee_team = employee_profile.team
    except WorkerProfile.DoesNotExist:
        messages.error(request, 'Pracownik nie ma przypisanego zespołu.')
        return redirect('all_requests_list')

    #2. Walidacja dla Managera
    if active_role == 'Manager':
        try:
            my_profile = WorkerProfile.objects.get(user=request.user)
        except WorkerProfile.DoesNotExist:
            messages.error(request, 'Nie masz przypisanego zespołu.')
            return redirect('all_requests_list')

        same_team = my_profile.team == employee_team
        is_worker = leave_request.employee.role == 'Worker'

        if not (same_team and is_worker):
            messages.error(request, 'Możesz akceptować tylko wnioski pracowników z Twojego zespołu.')
            return redirect('all_requests_list')

    # 3. Walidacja dla HR
    elif active_role == 'HR':
        if leave_request.employee == request.user.id:
            messages.error(request, 'Nie możesz akceptować własnego wniosku.')
            return redirect('all_requests_list')

    try:
        leave_request.approve(who=request.user)
        try:
            profile = WorkerProfile.objects.get(user=leave_request.employee)
            profile.subtract_leave_days(leave_request.amount_days)
        except WorkerProfile.DoesNotExist:
            pass
        messages.success(request, f'Wniosek od {leave_request.employee.first_name} {leave_request.employee.last_name} został zatwierdzony.')
    except Exception as e:
        messages.error(request, f'Błąd podczas zatwierdzania: {e}')

    return redirect('all_requests_list')


@login_required
@role_required("can_reject_request")
@require_POST
def reject_request(request, request_id):
    leave_request = get_object_or_404(LeaveRequest, pk=request_id)
    active_role = request.session.get('active_role', request.user.role)

    # 1. Pobierz zespół pracownika składającego wniosek
    try:
        employee_profile = WorkerProfile.objects.get(user=leave_request.employee)
        employee_team = employee_profile.team
    except WorkerProfile.DoesNotExist:
        messages.error(request, 'Pracownik nie ma przypisanego zespołu.')
        return redirect('all_requests_list')

    # 2. Walidacja dla Managera
    if active_role == 'Manager':
        try:
            my_profile = WorkerProfile.objects.get(user=request.user)
        except WorkerProfile.DoesNotExist:
            messages.error(request, 'Nie masz przypisanego zespołu.')
            return redirect('all_requests_list')

        same_team = my_profile.team == employee_team
        is_worker = leave_request.employee.role == 'Worker'

        if not (same_team and is_worker):
            messages.error(request, 'Możesz odrzucać tylko wnioski pracowników z Twojego zespołu.')
            return redirect('all_requests_list')

    # 3. Walidacja dla HR
    elif active_role == 'HR':
        if leave_request.employee == request.user.id:
            messages.error(request, 'Nie możesz odrzucać własnego wniosku.')
            return redirect('all_requests_list')


    # 4. Proces odrzucania wniosku
    try:
        leave_request.reject(who=request.user)
        messages.success(request, f'Wniosek od {leave_request.employee.first_name} {leave_request.employee.last_name} został odrzucony.')
    except Exception as e:
        messages.error(request, f'Błąd podczas odrzucania: {e}')

    return redirect('all_requests_list')

class LeaveRequestView(RoleRequiredMixin, CreateView):
    """
     Widok odpowiedzialny za tworzenie nowego wniosku urlopowego.
     Wymaga zalogowania użytkownika.
    """
    required_action = "can_submit_request"
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
        self.object = obj
        return redirect(self.get_success_url())

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

class LeaveRequestUpdateView(RoleRequiredMixin,UpdateView):
    """
    Widok odpowiedzialny za edycję istniejącego wniosku urlopowego.
    Zawiera walidację uprawnień oraz stanu wniosku.
    """
    required_action = "can_change_request"
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'leaves/edit_request.html'
    success_url = reverse_lazy('my_vacations')

    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return self.handle_no_permission()

        active_role = request.session.get('active_role', request.user.role)
        if not Permission.verifyPermission(active_role, self.required_action):
            AuthLog.objects.create(
                user=request.user,
                username=None,
                action='access_denied_403',
                details=f'Brak permisji: {self.required_action}. Aktywna rola: {active_role}',
                ip_address=get_client_ip(request),
                severity='warning'
            )
            return redirect('home')

        obj = self.get_object()

        # Blokada edycji wniosków, które zostały już zaakceptowane lub odrzucone
        if obj.status != LeaveRequest.Status.PENDING:
            messages.error(request, "Można edytować tylko wnioski oczekujące.")
            return redirect('home')

        # Pracownik nie może edytować wniosków innych osób
        if active_role == 'Worker' and obj.employee != request.user:
            messages.error(request, "Możesz edytować tylko własne wnioski.")
            return redirect('home')

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
        return redirect(self.get_success_url())

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
class CancelLeaveView(RoleRequiredMixin, View):
    required_action = "can_cancel_request"

    def post(self, request, pk):
        leave_request = get_object_or_404(LeaveRequest, pk=pk)
        active_role = request.session.get('active_role', request.user.role)

        if active_role == 'Worker' and leave_request.employee != request.user:
            messages.error(request, "Możesz anulować tylko własne wnioski.")
            return redirect('my_vacations')

        if leave_request.status != LeaveRequest.Status.PENDING:
            messages.error(request, "Można anulować tylko wnioski oczekujące.")
            return redirect('my_vacations')

        leave_request.cancel_request(who=request.user)
        messages.success(request, "Wniosek został anulowany.")

        if active_role == 'Worker':
            return redirect('my_vacations')
        return redirect('home')

@login_required
@role_required("can_see_team_balance")
def team_leave_balance(request):
    # Tylko Manager i HR mają dostęp
    active_role = request.session.get('active_role', request.user.role)
    if active_role not in ['Manager', 'HR', 'Admin']:
        return redirect('home')

    if active_role == 'HR':
        # HR widzi wszystkie zespoły
        all_team_names = (
            WorkerProfile.objects
            .values_list('team', flat=True)
            .distinct()
            .order_by('team')
        )

        teams = []
        for team_name in all_team_names:
            profiles = WorkerProfile.objects.filter(team=team_name).select_related('user')
            team_data = []
            for profile in profiles:
                team_data.append({
                    'first_name': profile.user.first_name,
                    'last_name': profile.user.last_name,
                    'total_days': profile._get_total_leave_days(),
                    'used_days': profile.used_leave_days,
                    'remaining_days': profile.get_leave_days(),
                })
            teams.append({
                'team_name': team_name,
                'team_data': team_data,
            })

        context = {
            'teams': teams,
            'is_hr': True,
        }

    else:
        # Manager widzi tylko swój zespół
        try:
            my_profile = WorkerProfile.objects.get(user=request.user)
            team_name = my_profile.team
        except WorkerProfile.DoesNotExist:
            team_name = None

        team_data = []
        if team_name:
            profiles = WorkerProfile.objects.filter(team=team_name).select_related('user')
            for profile in profiles:
                team_data.append({
                    'first_name': profile.user.first_name,
                    'last_name': profile.user.last_name,
                    'total_days': profile._get_total_leave_days(),
                    'used_days': profile.used_leave_days,
                    'remaining_days': profile.get_leave_days(),
                })

        context = {
            'teams': [{'team_name': team_name, 'team_data': team_data}],
            'is_hr': False,
        }

    return render(request, 'leaves/team_leave_balance.html', context)


@login_required
@role_required("can_export_requests")
def export_requests_csv(request):
    # tylko Manager i HR mają dostęp
    active_role = request.session.get('active_role', request.user.role)
    if active_role not in ['Manager', 'HR', 'Admin']:
        return redirect('home')

    # filtry z adresu URL
    status_filter = request.GET.get('status', '').lower()
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')

    # punkt wyjścia - wszystkie wnioski
    qs = LeaveRequest.objects.select_related('employee', 'who_confirmed').all()

    # Manager widzi tylko swój zespół — tak samo jak all_requests_list
    if active_role == 'Manager':
        try:
            my_profile = WorkerProfile.objects.get(user=request.user)
            team_members = WorkerProfile.objects.filter(team=my_profile.team).values_list('user', flat=True)
            qs = qs.filter(employee__in=team_members)
        except WorkerProfile.DoesNotExist:
            qs = qs.none()

    # filtruję po statusie
    if status_filter and status_filter in LeaveRequest.Status.values:
        qs = qs.filter(status=status_filter)

    # filtruję po datach
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            qs = qs.filter(end_date__gte=date_from)
        except ValueError:
            pass  # zignoruj jeśli data jest nieprawidłowa

    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            qs = qs.filter(start_date__lte=date_to)
        except ValueError:
            pass    # zignoruj jeśli data jest nieprawidłowa


    # odpowiedź HTTP jako plik CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="wnioski_urlopowe.csv"'

    writer = csv.writer(response)

    # nagłówki kolumn
    writer.writerow([
        'ID', 'Imię', 'Nazwisko', 'Data od', 'Data do',
        'Liczba dni', 'Status', 'Potwierdził', 'Data złożenia'
    ])

    # dane z bazy
    for req in qs:
        try:
            team = req.employee.worker_profile.team
        except Exception:
            team = ''

        writer.writerow([
            req.id,
            req.employee.first_name,
            req.employee.last_name,
            req.start_date,
            req.end_date,
            req.amount_days,
            req.get_status_display(),
            f"{req.who_confirmed.last_name} {req.who_confirmed.first_name}" if req.who_confirmed else '',
            req.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response

@login_required
@role_required("can_see_team_calendar")
def team_calendar(request):
    # miesięczny kalendarz urlopów dla całego zespołu
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

    pending_leaves = LeaveRequest.objects.filter(
        employee__id__in=team_user_ids,
        status=LeaveRequest.Status.PENDING,
        start_date__lte=last_day,
        end_date__gte=first_day,
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

    pending_map = {}

    for leave in pending_leaves:
        current = max(leave.start_date, first_day)
        end = min(leave.end_date, last_day)

        while current <= end:
            day_num = current.day

            if day_num not in pending_map:
                pending_map[day_num] = []

            name = f"{leave.employee.last_name} {leave.employee.first_name}"
            if name not in pending_map[day_num]:
                pending_map[day_num].append(name)

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
                week_row.append({'day': 0, 'leaves': [], 'pending': [], 'is_today': False})
            else:
                week_row.append({
                    'day': day_num,
                    'leaves': leave_map.get(day_num, []),  # [] jeśli brak urlopów
                    'pending': pending_map.get(day_num, []),
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




MONTH_NAMES_PL = [
    "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
    "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień",
]


def month_range(start_date, end_date):
    """Generuje kolejne pary (rok, miesiąc) pokrywające zakres dat."""
    year, month = start_date.year, start_date.month
    end_year, end_month = end_date.year, end_date.month

    while (year, month) <= (end_year, end_month):
        yield year, month
        month, year = (1, year + 1) if month == 12 else (month + 1, year)


def build_leave_calendars(leave):
    """Buduje listę kalendarzy miesięcznych z zaznaczonymi dniami urlopu."""
    cal = calendar.Calendar(firstweekday=0)
    calendars_data = []

    for year, month in month_range(leave.start_date, leave.end_date):
        cal_utils = Calendar_utils(year)

        leave_days_set = {
            d.day
            for d in _iter_month_overlap(leave.start_date, leave.end_date, year, month)
            if cal_utils.is_working_day(d)
        }

        weeks_data = []
        for week in cal.monthdayscalendar(year, month):
            week_days = []
            for day in week:
                if day == 0:
                    week_days.append({'day': '', 'is_leave': False, 'is_non_working': False})
                    continue

                check_date = date(year, month, day)
                week_days.append({
                    'day': day,
                    'is_leave': day in leave_days_set,
                    'is_non_working': cal_utils.is_weekend(check_date) or cal_utils.is_holiday(check_date),
                })
            weeks_data.append(week_days)

        calendars_data.append({
            'title': f"{MONTH_NAMES_PL[month - 1]} {year}",
            'weeks': weeks_data,
        })

    return calendars_data


def _iter_month_overlap(start_date, end_date, year, month):
    """Zwraca daty z zakresu [start_date, end_date] należące do danego (year, month)."""
    first_of_month = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last_of_month = date(year, month, last_day)

    range_start = max(start_date, first_of_month)
    range_end = min(end_date, last_of_month)

    current = range_start
    while current <= range_end:
        yield current
        current += timedelta(days=1)


class LeaveDetailView(LoginRequiredMixin, DetailView):
    model = LeaveRequest
    template_name = 'leaves/leave_detail.html'

    def get(self, request, *args, **kwargs):
        leave_request = get_object_or_404(LeaveRequest, pk=kwargs.get('pk'))
        target_user = leave_request.employee
        active_role = request.session.get('active_role', request.user.role)

        if not self._has_access(request.user, target_user, active_role):
            self._log_access_denied(request, leave_request, target_user, active_role)
            messages.info(request, 'Nie masz uprawnień do przeglądania tego wniosku')
            return redirect('home')

        context = self._build_context(request.user, leave_request, target_user, active_role)
        return self.render_to_response(context)

    def _log_access_denied(self, request, leave_request, target_user, active_role):
        AuthLog.objects.create(
            user=request.user,
            username=None,
            action='access_denied_403',
            details=(
                f"Próba podglądu wniosku #{leave_request.id} użytkownika "
                f"{target_user.username}. Aktywna rola: {active_role}"
            ),
            ip_address=get_client_ip(request),
            severity='warning',
        )

    def _has_access(self, viewer, target_user, active_role):
        if target_user == viewer:
            return True
        if active_role == 'Admin':
            return True
        if active_role == 'HR':
            return target_user.role not in ['HR', 'Admin']
        if active_role == 'Manager':
            return self._is_same_team_manager(viewer, target_user)
        return False

    def _is_same_team_manager(self, viewer, target_user):
        if target_user.role != "Worker":
            return False
        try:
            return viewer.worker_profile.team == target_user.worker_profile.team
        except WorkerProfile.DoesNotExist:
            return False

    def _build_context(self, viewer, leave, target_user, active_role):
        confirmed_by_name = None
        if leave.who_confirmed:
            confirmed_by = leave.who_confirmed
            confirmed_by_name = (
                f"{confirmed_by.first_name} {confirmed_by.last_name}".strip()
                or confirmed_by.username
            )

        activity_logs = ActivityLog.objects.filter(
            object_type='leave_request',
            object_id=leave.id,
        ).order_by('-created_at')[:10].values('created_at', 'details')

        return {
            'leave_id': leave.id,
            'owner_full_name': f"{target_user.first_name} {target_user.last_name}".strip() or target_user.username,
            'status_code': leave.status.lower(),
            'status_display': leave.get_status_display(),
            'start_date': leave.start_date,
            'end_date': leave.end_date,
            'amount_days': leave.amount_days,
            'confirmed_by_name': confirmed_by_name,
            'activity_logs': activity_logs,
            'calendars': build_leave_calendars(leave),
            'is_owner': viewer == target_user,
            'active_role': active_role,
            'target_user': target_user,
            'leave': leave,
        }