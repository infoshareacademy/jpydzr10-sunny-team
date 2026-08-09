import calendar
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView, View

from accounts.permission import RoleRequiredMixin
from leaves.models import LeaveRequest, WorkerProfile
from leaves.utils import Calendar_utils
from logs.models import ActivityLog, AuthLog
from logs.utils import get_client_ip

from .forms import TeamForm, TeamMembersForm
from .models import Team


class TeamListView(RoleRequiredMixin, ListView):
    """Widok listy zespołów."""

    required_action = "can_manage_team"
    model = Team
    template_name = "team/team_list.html"
    paginate_by = 5
    context_object_name = "teams"

    def dispatch(self, request, *args, **kwargs):
        """
        Logika przekierowań (UX):
        - Manager: przekierowanie do szczegółów swojego zespołu.
        - HR posiadający dokładnie 1 zespół: automatyczne przekierowanie do szczegółów tego zespołu.
        - HR posiadający >1 zespołów: wyświetlenie listy jego zespołów.
        - Admin: wyświetlenie listy wszystkich zespołów w podziale na aktywne i nieaktywne.
        """
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response

        active_role = request.session.get("active_role", request.user.role)

        if active_role == "Manager":
            managed_team = Team.objects.for_user(request.user).filter(is_active=True).first()
            if managed_team:
                return redirect("team-detail", pk=managed_team.pk)
            messages.warning(request, _("Nie jesteś przypisany jako manager do żadnego aktywnego zespołu."))
            return redirect("home")

        if active_role == "HR":
            hr_teams = Team.objects.filter(is_active=True, hr=request.user)
            teams_count = hr_teams.count()

            if teams_count == 1:
                single_team = hr_teams.first()
                return redirect("team-detail", pk=single_team.pk)

            elif teams_count == 0:
                messages.info(request, _("Nie jesteś obecnie opiekunem żadnego aktywnego zespołu."))
                return redirect("home")

            return response
        return response

    def get_queryset(self):
        """Zwraca bazowe aktywne zespoły odpowiednio przefiltrowane pod kątem roli."""
        active_role = self.request.session.get("active_role", self.request.user.role)
        base_qs = Team.objects.select_related("manager", "hr")

        if active_role == "Admin":
            return base_qs.filter(is_active=True)

        if active_role == "HR":
            return base_qs.filter(is_active=True, hr=self.request.user)

        return Team.objects.none()

    def get_context_data(self, **kwargs):
        """Przekazuje dane do szablonu z podziałem dla Admina (aktywne / nieaktywne)."""
        context = super().get_context_data(**kwargs)
        active_role = self.request.session.get("active_role", self.request.user.role)

        context["active_role"] = active_role

        if active_role == "Admin":
            context["active_teams"] = self.get_queryset()
            context["inactive_teams"] = Team.objects.filter(is_active=False).select_related("manager", "hr")
        else:
            context["active_teams"] = context["teams"]
            context["inactive_teams"] = Team.objects.none()

        return context


PL_MONTHS = {
    1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień", 5: "Maj", 6: "Czerwiec",
    7: "Lipiec", 8: "Sierpień", 9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień",
}

COLOR_PALETTE = [
    '#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed',
    '#db2777', '#0891b2', '#65a30d', '#ea580c', '#4f46e5',
]
DEFAULT_MEMBER_COLOR = '#94a3b8'
PENDING_STATUSES = ('pending', 'PENDING', '1')
APPROVED_AND_PENDING_STATUSES = ('APPROVED', 'PENDING', '1', '2')

EDIT_ROLES = ('HR', 'COO', 'Admin')
DEACTIVATE_ROLES = ('COO', 'Admin')


class TeamDetailView(LoginRequiredMixin, DetailView):
    """Widok szczegółów AKTYWNEGO zespołu wraz z listą pracowników i kalendarzem urlopów."""
    model = Team
    template_name = "team/team_detail.html"
    context_object_name = "team"

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        self.object = self.get_object()

        active_role = request.session.get('active_role', getattr(request.user, 'role', ''))

        if not self.object.is_active:
            return redirect("team-archive-detail", pk=self.object.pk)

        if not self._has_access(request.user, self.object, active_role):
            self._log_access_denied(request, self.object, active_role)
            messages.info(request, _('Nie masz uprawnień do przeglądania tego zespołu'))
            return redirect("home")

        return super().dispatch(request, *args, **kwargs)

    def _has_access(self, viewer, team, active_role):
        if active_role == 'Admin':
            return True

        if active_role in ('Manager', 'HR'):
            managed_team_ids = Team.objects.for_user(viewer).values_list('pk', flat=True)
            return team.pk in managed_team_ids

        try:
            own_team_id = viewer.worker_profile.team_id
        except WorkerProfile.DoesNotExist:
            return False

        return own_team_id == team.pk

    def _log_access_denied(self, request, team, active_role):
        AuthLog.objects.create(
            user=request.user,
            action='access_denied_403',
            details=format_lazy(
                _("Próba podglądu zespołu #{team_id} ({team_name}). Aktywna rola: {role}"),
                team_id=team.id,
                team_name=team.name,
                role=active_role,
            ),
            ip_address=get_client_ip(request),
            severity='warning',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object
        active_role = self.request.session.get('active_role', getattr(self.request.user, 'role', ''))

        context["can_edit_team"] = active_role in EDIT_ROLES
        context["can_deactivate"] = active_role in DEACTIVATE_ROLES

        manager_user = team.manager if (team.manager and team.manager.is_active) else None
        hr_user = team.hr if (team.hr and team.hr.is_active) else None

        context['manager_name'] = manager_user.get_full_name() if manager_user else _("Brak przypisanego")
        context['hr_name'] = hr_user.get_full_name() if hr_user else _("Brak przypisanego")

        team_profiles = self._get_team_profiles(team, manager_user, hr_user)
        member_users = [profile.user for profile in team_profiles]
        user_colors = self._build_user_colors(member_users)
        pending_counts = self._get_pending_counts(member_users)

        context['members_info'] = self._build_members_info(team_profiles, user_colors, pending_counts)
        context.update(self._build_calendar_data(member_users, user_colors))

        return context

    @staticmethod
    def _get_team_profiles(team, manager_user, hr_user):
        managers_and_hr = set(filter(None, [manager_user, hr_user]))
        return list(
            WorkerProfile.objects.filter(team=team, user__is_active=True)
            .exclude(user__in=managers_and_hr)
            .select_related('user')
            .order_by('user__last_name', 'user__first_name')
        )

    @staticmethod
    def _build_user_colors(member_users):
        return {user.id: COLOR_PALETTE[i % len(COLOR_PALETTE)] for i, user in enumerate(member_users)}

    @staticmethod
    def _get_pending_counts(member_users):
        pending_counts = {user.id: 0 for user in member_users}
        if not pending_counts:
            return pending_counts

        pending_leaves = LeaveRequest.objects.filter(
            employee_id__in=pending_counts.keys(),
            status__in=PENDING_STATUSES,
        ).values_list('employee_id', flat=True)

        for employee_id in pending_leaves:
            pending_counts[employee_id] += 1
        return pending_counts

    @staticmethod
    def _get_user_leave_stats(user):
        try:
            profile = user.worker_profile
            return profile.get_leave_days(), profile._get_total_leave_days()
        except AttributeError:
            return None, None

    @classmethod
    def _build_members_info(cls, team_profiles, user_colors, pending_counts):
        members_info = []
        for profile in team_profiles:
            leave_available, leave_total = cls._get_user_leave_stats(profile.user)
            members_info.append({
                'user': profile.user,
                'color': user_colors.get(profile.user.id, DEFAULT_MEMBER_COLOR),
                'leave_available': leave_available,
                'leave_total': leave_total,
                'pending_count': pending_counts.get(profile.user.id, 0),
            })
        return members_info

    def _get_calendar_month(self, today):
        try:
            month = int(self.request.GET.get('month', today.month))
            return month if 1 <= month <= 12 else today.month
        except (TypeError, ValueError):
            return today.month

    def _build_calendar_data(self, member_users, user_colors):
        today = date.today()
        year = today.year
        month = self._get_calendar_month(today)

        calendar_utils = Calendar_utils(year)
        month_days = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
        display_start, display_end = month_days[0][0], month_days[-1][-1]

        leaves_qs = LeaveRequest.objects.filter(
            employee_id__in=[user.id for user in member_users],
            start_date__lte=display_end,
            end_date__gte=display_start,
            status__in=APPROVED_AND_PENDING_STATUSES,
        ).select_related('employee').order_by('start_date')

        calendar_weeks = [
            self._build_week(
                week_dates, month, today, calendar_utils, leaves_qs,
                user_colors, display_start, display_end,
            )
            for week_dates in month_days
        ]

        return {
            'calendar_year': year,
            'calendar_month': month,
            'calendar_month_name': PL_MONTHS[month],
            'calendar_weeks': calendar_weeks,
            'calendar_prev_month': month - 1 if month > 1 else None,
            'calendar_next_month': month + 1 if month < 12 else None,
        }

    @classmethod
    def _build_week(cls, week_dates, month, today, calendar_utils, leaves_qs, user_colors,
                    display_start, display_end):
        week_start, week_end = week_dates[0], week_dates[-1]

        days_headers = [
            {
                'date': d, 'day': d.day, 'is_today': d == today,
                'is_other_month': d.month != month, 'is_weekend': d.weekday() >= 5,
                'is_working_day': calendar_utils.is_working_day(d),
            }
            for d in week_dates
        ]

        week_leaves = [
            cls._build_leave_bar(leave, week_start, week_end, calendar_utils, user_colors, display_start, display_end)
            for leave in leaves_qs
            if leave.start_date <= week_end and leave.end_date >= week_start
        ]
        return {'days_headers': days_headers, 'leaves': week_leaves}

    @staticmethod
    def _build_leave_bar(leave, week_start, week_end, calendar_utils, user_colors, display_start, display_end):
        render_start = max(leave.start_date, week_start)
        render_end = min(leave.end_date, week_end)

        start_col = (render_start - week_start).days + 1
        span = (render_end - render_start).days + 1

        non_working_days = [
            not calendar_utils.is_working_day(render_start + timedelta(days=offset))
            for offset in range(span)
        ]

        is_pending = str(leave.status).upper() in PENDING_STATUSES

        return {
            'id': leave.id,
            'user_id': leave.employee_id,
            'user_name': leave.employee.get_full_name() or leave.employee.username,
            'color': user_colors.get(leave.employee_id, DEFAULT_MEMBER_COLOR),
            'is_pending': is_pending,
            'status_display': _('Oczekujący') if is_pending else _('Zaakceptowany'),
            'start_col': start_col,
            'span': span,
            'non_working_days': non_working_days,
            'is_first_visible_segment': week_start <= max(leave.start_date, display_start) <= week_end,
            'show_prev_arrow': week_start == display_start and leave.start_date < display_start,
            'show_next_arrow': week_end == display_end and leave.end_date > display_end,
            'amount_days': getattr(leave, 'amount_days', (leave.end_date - leave.start_date).days + 1),
        }


class TeamArchiveDetailView(LoginRequiredMixin, DetailView):
    """
    Widok szczegółów ZARCHIWIZOWANEGO (nieaktywnego) zespołu.
    Zespół po soft_delete() nie ma już przypisanych pracowników/managera/HR,
    więc dane odtwarzane są na podstawie historycznych wpisów LeaveRequest.team,
    które są snapshotem z momentu złożenia wniosku.
    """
    model = Team
    template_name = "team/team_archive_detail.html"
    context_object_name = "team"

    ARCHIVED_REQUESTS_PER_PAGE = 15

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        self.object = self.get_object()

        active_role = request.session.get('active_role', getattr(request.user, 'role', ''))

        if self.object.is_active:
            return redirect("team-detail", pk=self.object.pk)

        if active_role != 'Admin':
            self._log_access_denied(request, self.object, active_role)
            messages.info(request, _('Tylko administrator może przeglądać zarchiwizowane zespoły.'))
            return redirect("home")

        return super().dispatch(request, *args, **kwargs)

    def _log_access_denied(self, request, team, active_role):
        AuthLog.objects.create(
            user=request.user,
            action='access_denied_403',
            details=format_lazy(
                _("Próba podglądu zarchiwizowanego zespołu #{team_id} ({team_name}). Aktywna rola: {role}"),
                team_id=team.id,
                team_name=team.name,
                role=active_role,
            ),
            ip_address=get_client_ip(request),
            severity='warning',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object

        historical_requests = (
            LeaveRequest.objects
            .filter(team_id=team.pk)
            .select_related('employee')
            .order_by('-start_date')
        )

        seen = {}
        for req in historical_requests:
            emp = req.employee
            if emp.id not in seen:
                seen[emp.id] = {
                    'user': emp,
                    'full_name': emp.get_full_name() or emp.username,
                    'is_active': emp.is_active,
                }
        archived_members = sorted(
            seen.values(),
            key=lambda m: ((m['user'].last_name or '').lower(), (m['user'].first_name or '').lower())
        )

        paginator = Paginator(historical_requests, self.ARCHIVED_REQUESTS_PER_PAGE)
        page_number = self.request.GET.get('page')
        archived_requests_page = paginator.get_page(page_number)

        context['archived_members'] = archived_members
        context['archived_members_count'] = len(archived_members)
        context['archived_requests'] = archived_requests_page

        return context


class TeamCreateView(RoleRequiredMixin, CreateView):
    """
    Widok tworzenia nowego zespołu.
    Dostępny wyłącznie dla Administratora systemu.
    """
    required_action = "can_manage_team"
    model = Team
    form_class = TeamForm
    template_name = "team/team_form.html"
    success_url = reverse_lazy("team-list")

    def dispatch(self, request, *args, **kwargs):
        """
        Weryfikuje, czy żądanie tworzenia zespołu pochodzi od Administratora.
        Brak uprawnień skutkuje komunikatem błędu i przekierowaniem na stronę główną.
        """
        if request.user.role != "Admin":
            messages.error(request, _("Brak uprawnień. Tylko Administrator może tworzyć nowe zespoły."))
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """
        Przekazuje zalogowanego użytkownika (request.user) do instancji formularza,
        co pozwala na weryfikację uprawnień do pól wewnątrz TeamForm.
        """
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """
        Obsługuje poprawny zapis formularza: tworzy obiekt zespołu w bazie,
        rejestruje zdarzenie w logach aktywności oraz dodaje komunikat dla użytkownika.
        """
        response = super().form_valid(form)

        log_details = form.generate_log_details(is_create=True)
        ActivityLog.objects.create(
            who=self.request.user,
            action="create",
            object_type="team",
            object_id=self.object.pk,
            severity="info",
            details=log_details,
        )

        messages.success(
            self.request,
            format_lazy(_("Pomyślnie utworzono zespół '{name}'."), name=self.object.name),
        )
        return response


class TeamUpdateView(RoleRequiredMixin, UpdateView):
    """
    Widok edycji podstawowych danych zespołu (nazwa, opis, manager, hr).
    """
    required_action = "can_manage_team"
    model = Team
    form_class = TeamForm
    template_name = "team/team_form.html"

    def get_success_url(self):
        return reverse("team-detail", kwargs={"pk": self.object.pk})

    def get_queryset(self):
        """Zapewnia dostęp tylko do aktywnych zespołów (nieusuniętych miękko)."""
        return Team.objects.filter(is_active=True)

    def dispatch(self, request, *args, **kwargs):
        """
        Weryfikuje szczegółowe uprawnienia przed przetworzeniem żądania:
        - Admin: ma dostęp do każdego zespołu.
        - HR: ma dostęp tylko do zespołu, do którego jest przypisany jako opiekun HR.
        Inne role oraz nieprzypisany HR są przekierowywani na stronę główną.
        """
        team = self.get_object()
        user = request.user

        is_admin = user.role == "Admin"
        is_assigned_hr = (user.role == "HR") and (team.hr_id == user.id)

        if not (is_admin or is_assigned_hr):
            messages.error(
                request,
                _("Brak uprawnień. Możesz edytować dane tylko tego zespołu, którego jesteś opiekunem HR."),
            )
            return redirect("home")

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """Przekazuje zalogowanego użytkownika do instancji TeamForm."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Zapisuje zmienione dane zespołu, tworzy wpis w ActivityLog i wywoływany jest komunikat sukcesu."""
        response = super().form_valid(form)

        log_details = form.generate_log_details(is_create=False)
        ActivityLog.objects.create(
            who=self.request.user,
            action="update",
            object_type="team",
            object_id=self.object.pk,
            severity="info",
            details=log_details,
        )

        messages.success(
            self.request,
            format_lazy(_("Pomyślnie zaktualizowano dane zespołu '{name}'."), name=self.object.name),
        )
        return response


class TeamDeleteView(RoleRequiredMixin, DeleteView):
    """
    Widok miękkiego usuwania (dezaktywacji) zespołu.
    Dostępny wyłącznie dla Administratora systemu.
    """
    required_action = "can_manage_team"
    model = Team
    template_name = "team/team_confirm_delete.html"
    success_url = reverse_lazy("team-list")

    def get_queryset(self):
        """Zapewnia dostęp tylko do aktywnych zespołów."""
        return Team.objects.filter(is_active=True)

    def dispatch(self, request, *args, **kwargs):
        """Weryfikuje, czy żądanie usunięcia pochodzi od Administratora."""
        if request.user.role != "Admin":
            messages.error(request, _("Brak uprawnień. Tylko Administrator może dezaktywować zespół."))
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Wykonuje miękkie usunięcie zespołu i rejestruje log ostrzegawczy."""
        team = self.get_object()
        team_name = team.name
        team_id = team.pk

        team.soft_delete()

        ActivityLog.objects.create(
            who=self.request.user,
            action="delete",
            object_type="team",
            object_id=team_id,
            severity="warning",
            details=str(format_lazy(_("Dezaktywowano zespół '{name}'."), name=team_name)),
        )

        messages.success(
            self.request,
            format_lazy(_("Zespół '{name}' został pomyślnie dezaktywowany."), name=team_name),
        )
        return redirect(self.success_url)


class TeamMembersUpdateView(RoleRequiredMixin, FormView):
    """
    Widok zarządzania składem osobowym zespołu (przypisywanie i odpinanie pracowników).
    """
    required_action = "can_manage_team"
    form_class = TeamMembersForm
    template_name = "team/team_members_form.html"

    def dispatch(self, request, *args, **kwargs):
        """
        Pobiera aktywny zespół i weryfikuje czy użytkownik ma uprawnienia do zarządzania jego składem:
        - Admin: zawsze ma dostęp
        - Manager: gdy jest przypisanym managerem tego zespołu
        - HR: gdy jest przypisanym opiekunem HR tego zespołu
        """
        self.team = get_object_or_404(Team, pk=kwargs["pk"], is_active=True)
        user = request.user

        is_admin = user.role == "Admin"
        is_assigned_manager = (user.role == "Manager") and (self.team.manager_id == user.id)
        is_assigned_hr = (user.role == "HR") and (self.team.hr_id == user.id)

        if not (is_admin or is_assigned_manager or is_assigned_hr):
            messages.error(
                request,
                _("Brak uprawnień. Możesz zarządzać składem osobowym tylko przypisanego do Ciebie zespołu."),
            )
            return redirect("home")

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """Przekazuje instancję zespołu do formularza w celu przefiltrowania pracowników."""
        kwargs = super().get_form_kwargs()
        kwargs["team"] = self.team
        return kwargs

    def get_context_data(self, **kwargs):
        """Udostępnia obiekt zespołu w kontekście szablonu HTML."""
        context = super().get_context_data(**kwargs)
        context["team"] = self.team
        return context

    def form_valid(self, form):
        """Zapisuje zmieniony skład członków zespołu, generuje wpis w ActivityLog i wyświetla komunikat."""
        form.save()

        log_details = form.generate_log_details()
        ActivityLog.objects.create(
            who=self.request.user,
            action="update",
            object_type="team",
            object_id=self.team.pk,
            severity="info",
            details=log_details,
        )

        messages.success(
            self.request,
            format_lazy(_("Pomyślnie zaktualizowano skład zespołu '{name}'."), name=self.team.name),
        )
        return super().form_valid(form)

    def get_success_url(self):
        """Przekierowanie po pomyślnym zapisie składu zespołu."""
        return reverse("team-detail", kwargs={"pk": self.team.pk})