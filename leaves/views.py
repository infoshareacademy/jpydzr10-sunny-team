from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import datetime, date, timedelta

from django.utils import timezone
from django.utils.text import format_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView, View, DetailView
from django.contrib import messages
from accounts.permission import Permission, role_required, RoleRequiredMixin
from leaves.models import LeaveRequest, WorkerProfile
import csv
from django.http import HttpResponse
import calendar
from accounts.models import User
from logs.models import AuthLog, ActivityLog
from logs.utils import get_client_ip
from team.models import Team
from .forms import LeaveRequestForm
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from mail.utils import send_approval_notification, send_reject_notification, send_new_request_notification
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from .utils import Calendar_utils


def _apply_common_filters_and_pagination(request, qs, page_size=10):
    """
    Pomocnicza funkcja nakładająca filtry GET, sortowanie oraz paginację.
    """
    search_query = request.GET.get('search', '').strip()
    selected_team_id = request.GET.get('team', '').strip()
    date_from_str = request.GET.get('date_from', '').strip()
    date_to_str = request.GET.get('date_to', '').strip()
    selected_status = request.GET.get('status', '').strip()
    order = request.GET.get('order', 'desc').strip()

    # Wyszukiwanie frazy
    if search_query:
        qs = qs.filter(
            Q(employee__first_name__icontains=search_query) |
            Q(employee__last_name__icontains=search_query) |
            Q(employee__username__icontains=search_query)
        )

    # Filtr zespołu
    if selected_team_id.isdigit():
        qs = qs.filter(employee__worker_profile__team_id=selected_team_id)

    # Filtr dat
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

    # Filtr statusu (jeśli przekazano)
    if selected_status:
        qs = qs.filter(status=selected_status)

    # Sortowanie
    ordering_field = 'created_at' if order == 'asc' else '-created_at'
    qs = qs.order_by(ordering_field)

    # Paginacja
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    filters_context = {
        'search': search_query,
        'team': int(selected_team_id) if selected_team_id.isdigit() else '',
        'date_from': date_from_str,
        'date_to': date_to_str,
        'status': selected_status,
        'order': order,
    }

    return page_obj, filters_context


@login_required
@role_required("can_see_all_requests")
def pending_requests_list(request):
    """Widok 1: Wnioski oczekujące na akceptację (PENDING) z filtracją i paginacją."""
    user = request.user
    active_role = request.session.get('active_role', user.role)

    # Ustalenie zespołów, z których wnioski użytkownik MOŻE rozpatrywać
    if active_role == 'Admin':
        approvable_teams = Team.objects.all()
    elif active_role == 'Manager':
        approvable_teams = Team.objects.filter(manager=user)
    elif active_role == 'HR':
        # HR widzi wnioski PENDING tylko z zespołów, których manager przebywa na urlopie
        approvable_teams = Team.objects.manageable_by(user, active_role=active_role)

    else:
        approvable_teams = Team.objects.none()

    # Bazowy QuerySet — tylko wnioski PENDING z dozwolonych zespołów
    qs = LeaveRequest.objects.filter(
        status=LeaveRequest.Status.PENDING,
        employee__worker_profile__team__in=approvable_teams
    ).select_related('employee', 'employee__worker_profile__team')

    # Aplikujemy filtry i paginację
    pending_page, filters_context = _apply_common_filters_and_pagination(request, qs)

    context = {
        'managed_teams': approvable_teams,
        'pending_requests': pending_page,
        'status_choices': LeaveRequest.Status.choices,
        'can_approve': active_role in ('Manager', 'HR', 'Admin'),
        'filters': filters_context,
    }
    return render(request, 'leaves/pending_requests_list.html', context)


@login_required
@role_required("can_see_all_requests")
def history_requests_list(request):
    """Widok 2: Historia wniosków (wszystkie widoczne zespoły) z filtracją i paginacją."""
    user = request.user
    active_role = request.session.get('active_role', user.role)

    # Zespoły widoczne ogólnie w historii
    if active_role == 'Admin':
        visible_teams = Team.objects.all()
    elif active_role == 'Manager':
        visible_teams = Team.objects.filter(manager=user)
    elif active_role == 'HR':
        visible_teams = Team.objects.filter(hr=user)
    else:
        visible_teams = Team.objects.none()

    # Bazowy QuerySet — wykluczamy PENDING
    qs = LeaveRequest.objects.filter(
        employee__worker_profile__team__in=visible_teams
    ).exclude(
        status=LeaveRequest.Status.PENDING
    ).select_related('employee', 'employee__worker_profile__team')

    # Aplikujemy filtry i paginację
    history_page, filters_context = _apply_common_filters_and_pagination(request, qs)

    context = {
        'managed_teams': visible_teams,
        'history_requests': history_page,
        'status_choices': LeaveRequest.Status.choices,
        'can_approve': active_role in ('Manager', 'HR', 'Admin'),
        'filters': filters_context,
    }
    return render(request, 'leaves/history_requests_list.html', context)

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

def _can_act_on_request(user, active_role, leave_request):
    """
    Manager/HR może działać na wniosku, jeśli zespół pracownika
    znajduje się w zbiorze zespołów zarządzanych przez tego usera
    (dla HR: manager nieobecny lub brak managera).
    Rola/stanowisko wnioskodawcy nie ma znaczenia.
    """
    if active_role not in ('Manager', 'HR'):
        return False

    try:
        team_id = leave_request.employee.worker_profile.team_id
    except WorkerProfile.DoesNotExist:
        return False

    if not team_id:
        return False

    manageable_team_ids = Team.objects.manageable_by(
        user, active_role=active_role
    ).values_list('pk', flat=True)

    return team_id in manageable_team_ids

@login_required
@role_required("can_approve_request")
@require_POST
def approve_request(request, request_id):
    leave_request = get_object_or_404(LeaveRequest, pk=request_id)
    active_role = request.session.get('active_role', request.user.role)

    if not Permission.verifyPermission(active_role, 'can_approve_request'):
        messages.error(request, _('Nie masz uprawnień do zatwierdzania wniosków urlopowych.'))
        return redirect('pending_requests_list')

    if leave_request.employee_id == request.user.id:
        messages.error(request, _('Nie możesz akceptować własnego wniosku.'))
        return redirect('pending_requests_list')

    if not _can_act_on_request(request.user, active_role, leave_request):
        messages.error(
            request,
            _('Nie możesz akceptować tego wniosku')
        )
        return redirect('pending_requests_list')

    answer_comment = request.POST.get('answer_comment', '').strip()[:250]
    leave_request.answer_comment = answer_comment if answer_comment else None

    try:
        leave_request.approve(who=request.user)
        try:
            profile = WorkerProfile.objects.get(user=leave_request.employee)
            profile.subtract_leave_days(leave_request.amount_days)
        except WorkerProfile.DoesNotExist:
            pass
        messages.success(
            request,
            format_lazy(
                _('Wniosek od {first_name} {last_name} został zatwierdzony.'),
                first_name=leave_request.employee.first_name,
                last_name=leave_request.employee.last_name,
            )
        )
        try:
            send_approval_notification(
                employee_email=leave_request.employee.email,
                employee_name=f"{leave_request.employee.first_name} {leave_request.employee.last_name}",
                request_details=f"{leave_request.start_date} – {leave_request.end_date} ({leave_request.amount_days} dni)",
                site_url=settings.SITE_URL,
            )
        except Exception as mail_error:
            print(f"Błąd wysyłki powiadomienia e-mail: {mail_error}")
    except Exception as e:
        messages.error(
            request,
            format_lazy(_('Błąd podczas zatwierdzania: {error}'), error=e)
        )
    return redirect('pending_requests_list')


@login_required
@role_required("can_reject_request")
@require_POST
def reject_request(request, request_id):
    leave_request = get_object_or_404(LeaveRequest, pk=request_id)
    active_role = request.session.get('active_role', request.user.role)

    if not Permission.verifyPermission(active_role, 'can_reject_request'):
        messages.error(request, _('Nie masz uprawnień do odrzucania wniosków urlopowych.'))
        return redirect('pending_requests_list')

    if leave_request.employee_id == request.user.id:
        messages.error(request, _('Nie możesz odrzucać własnego wniosku.'))
        return redirect('pending_requests_list')

    if not _can_act_on_request(request.user, active_role, leave_request):
        messages.error(
            request,
            _('Nie możesz odrzucić tego wniosku.')
        )
        return redirect('pending_requests_list')

    answer_comment = request.POST.get('answer_comment', '').strip()[:250]
    leave_request.answer_comment = answer_comment if answer_comment else None

    try:
        leave_request.reject(who=request.user)
        messages.success(
            request,
            format_lazy(
                _('Wniosek od {first_name} {last_name} został odrzucony.'),
                first_name=leave_request.employee.first_name,
                last_name=leave_request.employee.last_name,
            )
        )
        try:
            send_reject_notification(
                employee_email=leave_request.employee.email,
                employee_name=f"{leave_request.employee.first_name} {leave_request.employee.last_name}",
                request_details=f"{leave_request.start_date} – {leave_request.end_date} ({leave_request.amount_days} dni)",
                rejection_reason=None,
                site_url=settings.SITE_URL,
            )
        except Exception as mail_error:
            print(f"Błąd wysyłki powiadomienia e-mail o odrzuceniu: {mail_error}")
    except Exception as e:
        messages.error(
            request,
            format_lazy(_('Błąd podczas odrzucania: {error}'), error=e)
        )
    return redirect('pending_requests_list')

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

        # --- WYŚLIJ MAIL DO MANAGERA/HR ---
        # Pobierz adresy email wszystkich użytkowników z rolą Manager lub HR
        User = get_user_model()
        manager_emails = list(
            User.objects.filter(role__in=["Manager", "HR"])
            .values_list("email", flat=True)
            .exclude(email="")
        )

        if manager_emails:
            try:
                send_new_request_notification(
                    manager_emails=manager_emails,
                    employee_name=f"{self.request.user.first_name} {self.request.user.last_name}",
                    request_details=f"{obj.start_date} – {obj.end_date} ({obj.amount_days} dni)",
                    submission_date=timezone.now().strftime("%Y-%m-%d %H:%M"),
                    site_url=settings.SITE_URL,
                )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Błąd wysyłki maila do managera: {e}")

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

        try:
            profile = WorkerProfile.objects.get(user=self.request.user)
            context['available_days'] = profile.get_leave_days()
        except WorkerProfile.DoesNotExist:
            context['available_days'] = None

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

        """
        Główna metoda kontrolująca dostęp do widoku. Sprawdza:
         1. Czy rola użytkownika pozwala ogólnie na modyfikację wniosków.
         2. Czy wniosek ma status "PENDING" (oczekujący) – tylko takie można edytować.
         3. Czy pracownik  próbuje edytować swój własny wniosek, a nie cudzy.
        """
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        active_role = request.session.get('active_role', request.user.role)
        if not Permission.verifyPermission(active_role, self.required_action):
            AuthLog.objects.create(
                user=request.user,
                action='access_denied_403',
                details=format_lazy(
                    _('Brak permisji: {action}. Aktywna rola: {role}'),
                    action=self.required_action,
                    role=active_role,
                ),
                ip_address=get_client_ip(request),
                severity='warning'
            )
            return redirect('home')

        obj = self.get_object()

        # Blokada edycji wniosków, które zostały już zaakceptowane lub odrzucone
        if obj.status != LeaveRequest.Status.PENDING:
            messages.error(request, _("Można edytować tylko wnioski oczekujące."))
            return redirect('home')

        # Pracownik nie może edytować wniosków innych osób
        if active_role == 'Worker' and obj.employee != request.user:
            messages.error(request, _("Możesz edytować tylko własne wnioski."))
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
            messages.error(request, _("Możesz anulować tylko własne wnioski."))
            return redirect('my_vacations')

        if leave_request.status != LeaveRequest.Status.PENDING:
            messages.error(request, _("Można anulować tylko wnioski oczekujące."))
            return redirect('my_vacations')

        answer_comment = request.POST.get('answer_comment', '').strip()[:250]
        leave_request.answer_comment = answer_comment if answer_comment else None

        leave_request.cancel_request(who=request.user)
        messages.success(request, _("Wniosek został anulowany."))

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

    # Manager widzi tylko swój zespół
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
            pass

    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            qs = qs.filter(start_date__lte=date_to)
        except ValueError:
            pass


    # odpowiedź HTTP jako plik CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="wnioski_urlopowe.csv"'

    writer = csv.writer(response)

    # nagłówki kolumn
    writer.writerow([
        str(_('ID')),
        str(_('Imię')),
        str(_('Nazwisko')),
        str(_('Zespół')),
        str(_('Data od')),
        str(_('Data do')),
        str(_('Liczba dni')),
        str(_('Status')),
        str(_('Potwierdził')),
        str(_('Data złożenia')),
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
            team,
            req.start_date,
            req.end_date,
            req.amount_days,
            req.get_status_display(),
            f"{req.who_confirmed.last_name} {req.who_confirmed.first_name}" if req.who_confirmed else '',
            req.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response

MONTH_NAMES_PL = [
    _("Styczeń"),
    _("Luty"),
    _("Marzec"),
    _("Kwiecień"),
    _("Maj"),
    _("Czerwiec"),
    _("Lipiec"),
    _("Sierpień"),
    _("Wrzesień"),
    _("Październik"),
    _("Listopad"),
    _("Grudzień"),
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
            'title': f"{str(MONTH_NAMES_PL[month - 1])} {year}",
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
            messages.info(request, _('Nie masz uprawnień do przeglądania tego wniosku'))
            return redirect('home')

        context = self._build_context(request.user, leave_request, target_user, active_role)
        return self.render_to_response(context)

    def _log_access_denied(self, request, leave_request, target_user, active_role):
        AuthLog.objects.create(
            user=request.user,
            action='access_denied_403',
            details=format_lazy(
                _("Próba podglądu wniosku #{request_id} użytkownika {username}. Aktywna rola: {active_role}"),
                request_id=leave_request.id,
                username=target_user.username,
                active_role=active_role,
            ),
            ip_address=get_client_ip(request),
            severity='warning',
        )

    def _managed_team_ids(self, viewer, active_role):
        if active_role in ('Manager', 'HR'):
            return set(Team.objects.for_user(viewer).values_list('pk', flat=True))
        return set()

    def _has_access(self, viewer, target_user, active_role, managed_team_ids=None):
        """
        - Worker (rola aktywna): dostęp TYLKO do własnych wniosków
        - Manager / HR: dostęp do wniosków osób z zarządzanych zespołów.
          WŁASNY wniosek NIE jest dostępny w tych rolach — trzeba przełączyć na Workera.
        - Admin: zawsze dostęp do wszystkiego
        """
        if active_role == 'Admin':
            return True

        if active_role == 'Worker':
            return target_user == viewer

        if active_role in ('Manager', 'HR'):
            if target_user == viewer:
                return False

            if managed_team_ids is None:
                managed_team_ids = self._managed_team_ids(viewer, active_role)
            try:
                target_team_id = target_user.worker_profile.team_id
            except WorkerProfile.DoesNotExist:
                return False
            return target_team_id in managed_team_ids

        return False

    def _base_visible_queryset(self, viewer, active_role):
        """
        Queryset używany do nawigacji strzałkami (prev/next) — musi dokładnie
        odzwierciedlać to, co przepuszcza _has_access.
        """
        if active_role == 'Admin':
            return LeaveRequest.objects.all()

        if active_role == 'Worker':
            return LeaveRequest.objects.filter(employee=viewer)

        if active_role in ('Manager', 'HR'):
            managed_team_ids = self._managed_team_ids(viewer, active_role)
            # własne wnioski WYKLUCZONE, bo _has_access ich nie przepuszcza w tej roli
            return LeaveRequest.objects.filter(
                employee__worker_profile__team_id__in=managed_team_ids
            ).exclude(employee=viewer).distinct()

        return LeaveRequest.objects.none()

    def _can_approve_or_reject(self, viewer, target_user, active_role, leave_request):
        """
        Uprawnienie do AKCEPTACJI/ODRZUCENIA:
        - Manager -> zawsze dla swojego zespołu
        - HR -> tylko gdy manager zespołu nieobecny (na zaakceptowanym urlopie) lub brak managera
        - własny wniosek -> nigdy
        - wniosek już rozpatrzony -> nie pokazujemy przycisków
        """
        if target_user == viewer:
            return False

        if leave_request.status != LeaveRequest.Status.PENDING:
            return False

        if active_role not in ('Manager', 'HR'):
            return False

        try:
            target_team_id = target_user.worker_profile.team_id
        except WorkerProfile.DoesNotExist:
            return False

        if target_team_id is None:
            return False

        manageable_team_ids = Team.objects.manageable_by(
            viewer, active_role=active_role
        ).values_list('pk', flat=True)

        return target_team_id in manageable_team_ids

    def _get_adjacent_leave_ids(self, viewer, current_leave, active_role):
        base_qs = self._base_visible_queryset(viewer, active_role)

        prev_id = (
            base_qs.filter(id__lt=current_leave.id)
            .order_by('-id')
            .values_list('id', flat=True)
            .first()
        )
        next_id = (
            base_qs.filter(id__gt=current_leave.id)
            .order_by('id')
            .values_list('id', flat=True)
            .first()
        )
        return prev_id, next_id

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
        ).order_by('-created_at')[:10]

        logs_data = [
            {
                'created_at': log.created_at,
                'action': log.action,
                'action_display': log.get_action_display(),
                'details': log.details,
            }
            for log in activity_logs
        ]

        # POPRAWIONE POBIERANIE ZESPOŁU
        profile = getattr(target_user, 'worker_profile', None) or getattr(target_user, 'workerprofile', None)
        team_obj = profile.team if (profile and profile.team_id) else None

        prev_id, next_id = self._get_adjacent_leave_ids(viewer, leave, active_role)

        return {
            'leave_id': leave.id,
            'owner_full_name': f"{target_user.first_name} {target_user.last_name}".strip() or target_user.username,
            'team': team_obj,
            'status_code': leave.status.lower(),
            'status_display': leave.get_status_display(),
            'start_date': leave.start_date,
            'end_date': leave.end_date,
            'amount_days': leave.amount_days,
            'confirmed_by_name': confirmed_by_name,
            'activity_logs': logs_data,
            'calendars': build_leave_calendars(leave),
            'is_owner': viewer == target_user,
            'active_role': active_role,
            'target_user': target_user,
            'leave': leave,
            'prev_id': prev_id,
            'next_id': next_id,
            'can_approve_or_reject': self._can_approve_or_reject(
                viewer, target_user, active_role, leave
            ),
        }