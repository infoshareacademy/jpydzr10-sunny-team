from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import datetime, date, timedelta

from django.utils import timezone
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
from .forms import LeaveRequestForm
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from mail.utils import send_approval_notification, send_reject_notification, send_new_request_notification
from django.conf import settings
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from .utils import Calendar_utils
from team.models import Team
from django.db.models import Q, Case, When, Value, IntegerField
from collections import defaultdict
from django.core.paginator import Paginator


def _get_manager_team_ids(user):
    return list(Team.get_teams_managed_by(user).values_list('pk', flat=True))


def _base_visible_queryset(request, active_role):
    qs = LeaveRequest.objects.select_related(
        'employee',
        'who_confirmed',
        'employee__worker_profile',
        'employee__worker_profile__team',
    )

    if active_role == 'Worker':
        return qs.filter(employee=request.user)

    if active_role == 'Manager':
        managed_team_ids = _get_manager_team_ids(request.user)
        if not managed_team_ids:
            return qs.none()

        team_members = WorkerProfile.objects.filter(
            team_id__in=managed_team_ids
        ).values_list('user', flat=True)

        return qs.filter(employee__in=team_members, employee__role='Worker')

    if active_role == 'HR':
        return qs.filter(employee__role__in=['Worker', 'Manager'])

    if active_role in ('COO', 'Admin'):
        return qs

    return qs.none()


def _get_role_and_team_lists(active_role, base_qs):
    if active_role == 'Manager':
        roles = []
        teams = Team.objects.filter(
            id__in=base_qs.values('employee__worker_profile__team')
        ).distinct()
    elif active_role == 'HR':
        roles = ['Worker', 'Manager']
        teams = Team.objects.filter(is_active=True)
    else:
        roles = ['Worker', 'Manager', 'HR', 'COO', 'Admin']
        teams = Team.objects.filter(is_active=True)

    return roles, teams


def _apply_filters_and_ordering(qs, filters, all_roles_list):
    if user_id := filters['user']:
        if user_id.isdigit():
            qs = qs.filter(employee_id=user_id)
    elif query := filters['search']:
        qs = qs.filter(
            Q(employee__first_name__icontains=query) |
            Q(employee__last_name__icontains=query) |
            Q(employee__username__icontains=query)
        )

    if status := filters['status']:
        if status in LeaveRequest.Status.values:
            qs = qs.filter(status=status)

    proc = filters['processed']
    if proc == 'unprocessed':
        qs = qs.filter(status='pending')
    elif proc == 'processed':
        qs = qs.filter(status__in=['approved', 'rejected', 'canceled'])
    elif proc in ('approved', 'rejected', 'canceled'):
        qs = qs.filter(status=proc)

    if date_from_str := filters['date_from']:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            qs = qs.filter(end_date__gte=date_from)
        except ValueError:
            pass

    if date_to_str := filters['date_to']:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            qs = qs.filter(start_date__lte=date_to)
        except ValueError:
            pass

    if (role := filters['role']) and role in all_roles_list:
        qs = qs.filter(employee__role=role)

    if team_id := filters['team']:
        if team_id.isdigit():
            qs = qs.filter(employee__worker_profile__team_id=team_id)

    return qs.annotate(
        role_priority=Case(
            When(employee__role='COO', then=Value(0)),
            When(employee__role='HR', then=Value(1)),
            When(employee__role='Manager', then=Value(2)),
            When(employee__role='Worker', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        ),
        status_priority=Case(
            When(status='pending', then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by(
        'role_priority',
        'employee__worker_profile__team__name',
        'status_priority',
        '-created_at'
    )


def _attach_managed_teams(requests_list):
    employee_ids = {req.employee_id for req in requests_list}
    has_manager_id_attr = hasattr(Team, 'manager_id')

    managed_teams_map = (
        {
            team.manager_id: list(team.managed_teams.all())
            for team in Team.objects.filter(manager_id__in=employee_ids).prefetch_related('managed_teams')
        }
        if has_manager_id_attr
        else {}
    )

    for req in requests_list:
        req.managed_teams = managed_teams_map.get(
            req.employee_id,
            list(Team.get_teams_managed_by(req.employee))
        )


def _build_section_data(items):
    pending = [r for r in items if r.status == 'pending']
    processed = [r for r in items if r.status != 'pending']
    return {
        'has_items': bool(items),
        'pending': pending,
        'processed': processed,
        'pending_count': len(pending),
        'processed_count': len(processed),
    }


def _get_team_for_employee(employee):
    try:
        return employee.worker_profile.team
    except (ObjectDoesNotExist, AttributeError):
        return None


def _build_page_sections(page_items):
    role_groups = defaultdict(list)
    worker_unassigned = []
    teams_on_page = defaultdict(lambda: {'team_name': '', 'requests': []})

    for req in page_items:
        role = req.employee.role
        if role in ('COO', 'HR', 'Manager'):
            role_groups[role].append(req)
        else:
            role_groups['Worker'].append(req)
            team = _get_team_for_employee(req.employee)
            if team:
                teams_on_page[team.id]['team_name'] = team.name
                teams_on_page[team.id]['requests'].append(req)
            else:
                worker_unassigned.append(req)

    worker_teams_list = [
        {
            'team_name': data['team_name'],
            'requests': _build_section_data(data['requests'])
        }
        for data in teams_on_page.values()
    ]

    return {
        'coo': _build_section_data(role_groups['COO']),
        'hr': _build_section_data(role_groups['HR']),
        'managers': _build_section_data(role_groups['Manager']),
        'workers': {
            'has_items': bool(role_groups['Worker']),
            'unassigned': _build_section_data(worker_unassigned),
            'teams': worker_teams_list,
        }
    }


@login_required
@role_required("can_see_all_requests")
def all_requests_list(request):
    active_role = request.session.get('active_role', request.user.role)
    base_qs = _base_visible_queryset(request, active_role)

    all_roles_list, all_teams_list = _get_role_and_team_lists(active_role, base_qs)

    filters = {
        'status': request.GET.get('status', '').lower(),
        'processed': request.GET.get('processed', '').lower(),
        'date_from': request.GET.get('date_from', ''),
        'date_to': request.GET.get('date_to', ''),
        'team': request.GET.get('team', ''),
        'role': request.GET.get('role', ''),
        'user': request.GET.get('user'),
        'search': request.GET.get('search', '').strip(),
    }

    queryset = _apply_filters_and_ordering(base_qs, filters, all_roles_list)

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    page_items = list(page_obj.object_list)
    _attach_managed_teams(page_items)

    sections = _build_page_sections(page_items)

    context = {
        'page_obj': page_obj,
        'sections': sections,
        'active_role': active_role,
        'proc_filter': filters['processed'],
        'status_filter': filters['status'],
        'date_from': filters['date_from'],
        'date_to': filters['date_to'],
        'team_filter': filters['team'],
        'role_filter': filters['role'],
        'search_query': filters['search'],
        'all_teams_list': all_teams_list,
        'all_roles_list': all_roles_list,
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
    if not Permission.verifyPermission(active_role, 'can_approve_request'):
        messages.error(request, 'Nie masz uprawnień do zatwierdzania wniosków urlopowych.')
        return redirect('all_requests_list')

    try:
        employee_profile = WorkerProfile.objects.get(user=leave_request.employee)
        employee_team_id = employee_profile.team_id
    except WorkerProfile.DoesNotExist:
        employee_team_id = None

    if active_role == 'Manager':
        managed_team_ids = _get_manager_team_ids(request.user)
        is_worker = leave_request.employee.role == 'Worker'
        same_team = employee_team_id in managed_team_ids
        if not (same_team and is_worker):
            messages.error(request, _('Możesz akceptować tylko wnioski pracowników z Twojego zespołu.'))
            return redirect('all_requests_list')

    elif active_role == 'HR':
        if leave_request.employee_id == request.user.id:
            messages.error(request, 'Nie możesz akceptować własnego wniosku.')
            return redirect('all_requests_list')
        if leave_request.employee.role not in ('Worker', 'Manager'):
            messages.error(request, 'HR może zatwierdzać jedynie wnioski Workerów i Managerów.')
            return redirect('all_requests_list')

    elif active_role in ('COO', 'Admin'):
        if leave_request.employee_id == request.user.id:
            messages.error(request, 'Nie możesz akceptować własnego wniosku.')
            return redirect('all_requests_list')

        answer_comment = request.POST.get('answer_comment', '').strip()[:250]
        leave_request.answer_comment = answer_comment if answer_comment else None

    try:
        leave_request.approve(who=request.user)
        try:
            profile = WorkerProfile.objects.get(user=leave_request.employee)
            profile.subtract_leave_days(leave_request.amount_days)
        except WorkerProfile.DoesNotExist:
            pass
        messages.success(request, f'Wniosek od {leave_request.employee.first_name} {leave_request.employee.last_name} został zatwierdzony.')
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
        messages.error(request, _(f'Błąd podczas zatwierdzania: {e}'))
    return redirect('all_requests_list')


@login_required
@role_required("can_reject_request")
@require_POST
def reject_request(request, request_id):
    leave_request = get_object_or_404(LeaveRequest, pk=request_id)
    active_role = request.session.get('active_role', request.user.role)

    if not Permission.verifyPermission(active_role, 'can_reject_request'):
        messages.error(request, 'Nie masz uprawnień do odrzucania wniosków urlopowych.')
        return redirect('all_requests_list')

    try:
        employee_profile = WorkerProfile.objects.get(user=leave_request.employee)
        employee_team_id = employee_profile.team_id
    except WorkerProfile.DoesNotExist:
        employee_team_id = None

    if active_role == 'Manager':
        managed_team_ids = _get_manager_team_ids(request.user)
        is_worker = leave_request.employee.role == 'Worker'
        same_team = employee_team_id in managed_team_ids
        if not (same_team and is_worker):
            messages.error(request, _('Możesz odrzucać tylko wnioski pracowników z Twojego zespołu.'))
            return redirect('all_requests_list')

    elif active_role == 'HR':
        if leave_request.employee_id == request.user.id:
            messages.error(request, 'Nie możesz odrzucać własnego wniosku.')
            return redirect('all_requests_list')
        if leave_request.employee.role not in ('Worker', 'Manager'):
            messages.error(request, 'HR może odrzucać jedynie wnioski Workerów i Managerów.')
            return redirect('all_requests_list')

    elif active_role in ('COO', 'Admin'):
        if leave_request.employee_id == request.user.id:
            messages.error(request, 'Nie możesz odrzucać własnego wniosku.')
            return redirect('all_requests_list')

    answer_comment = request.POST.get('answer_comment', '').strip()[:250]
    leave_request.answer_comment = answer_comment if answer_comment else None

    try:
        leave_request.reject(who=request.user)
        messages.success(request,
                         f'Wniosek od {leave_request.employee.first_name} {leave_request.employee.last_name} został odrzucony.')
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
        messages.error(request, _(f'Błąd podczas odrzucania: {e}'))

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

        user_role = getattr(self.request.user, "role", None)
        if user_role == "COO":
            obj.status = LeaveRequest.Status.APPROVED
            obj.who_confirmed = self.request.user
            try:
                profile = WorkerProfile.objects.get(user=self.request.user)
                profile.subtract_leave_days(obj.amount_days)
            except (WorkerProfile.DoesNotExist, ValueError) as e:
                pass

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
                details=f'Brak permisji: {self.required_action}. Aktywna rola: {active_role}',
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
        'ID', 'Imię', 'Nazwisko', 'Zespół', 'Data od', 'Data do',
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
        if active_role in ['Admin', 'COO']:
            return True
        if active_role == 'HR':
            return target_user.role not in ['HR', 'COO', 'Admin']
        if active_role == 'Manager':
            return self._is_same_team_manager(viewer, target_user)
        return False

    def _is_same_team_manager(self, viewer, target_user):
        if target_user.role != "Worker":
            return False
        try:
            target_team_id = target_user.worker_profile.team_id
        except WorkerProfile.DoesNotExist:
            return False
        if target_team_id is None:
            return False
        managed_team_ids = Team.get_teams_managed_by(viewer).values_list('pk', flat=True)
        return target_team_id in managed_team_ids

    def _get_adjacent_leave_ids(self, viewer, current_leave, active_role):
        """Wyznacza ID poprzedniego i następnego wniosku dostępnego dla użytkownika.

        Lista jest sortowana rosnąco po ID, aby strzałka w prawo prowadziła do wyższego ID,
        a strzałka w lewo do niższego ID.
        """
        # Sortujemy rosnąco po ID, aby zachować naturalną kolejność chronologiczną (1, 2, 3...)
        base_qs = _base_visible_queryset(self.request, active_role).order_by('id')

        leave_ids = list(base_qs.values_list('id', flat=True))

        try:
            current_index = leave_ids.index(current_leave.id)
            # Poprzedni w liście = mniejszy numer ID (strzałka w lewo)
            prev_id = leave_ids[current_index - 1] if current_index > 0 else None
            # Następny w liście = większy numer ID (strzałka w prawo)
            next_id = leave_ids[current_index + 1] if current_index < len(leave_ids) - 1 else None
        except ValueError:
            prev_id = None
            next_id = None

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

        user_teams = []
        if hasattr(target_user, 'worker_profile') and target_user.worker_profile.team:
            user_teams = [target_user.worker_profile.team]
        elif target_user.role == 'Manager':
            user_teams = list(Team.get_teams_managed_by(target_user))
        prev_id, next_id = self._get_adjacent_leave_ids(viewer, leave, active_role)

        return {
            'leave_id': leave.id,
            'owner_full_name': f"{target_user.first_name} {target_user.last_name}".strip() or target_user.username,
            'user_teams': user_teams,
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
        }