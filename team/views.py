from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, FormView

from accounts.permission import RoleRequiredMixin, Permission
from logs.models import ActivityLog
from .models import Team
from .forms import TeamForm,TeamMembersForm
from .permission import TeamDetailAccessMixin

from leaves.utils import Calendar_utils
import calendar
from datetime import date, timedelta
from leaves.models import WorkerProfile, LeaveRequest

class WarningMixin:
    def _warn_if_managers_overlap(self, form):
        head_manager = form.cleaned_data.get("head_manager")
        co_managers = form.cleaned_data.get("co_managers") or []

        for user in filter(None, [head_manager, *co_managers]):
            other_teams = Team.objects.filter(
                is_active=True
            ).filter(
                Q(head_manager=user) | Q(co_managers=user)
            ).exclude(pk=self.object.pk if self.object else None).distinct()

            if other_teams.exists():
                names = ", ".join(t.name for t in other_teams)
                messages.info(
                    self.request,
                    f"Uwaga: {user.get_full_name() or user.username} zarządza już "
                    f"zespołem/zespołami: {names}."
                )

    def form_valid(self, form):
        is_create = self.object is None or self.object.pk is None
        response = super().form_valid(form)

        self._warn_if_managers_overlap(form)

        log_details = form.generate_log_details(is_create=is_create)
        ActivityLog.objects.create(
            who=self.request.user,
            action='create' if is_create else 'update',
            object_type='team',
            object_id=self.object.pk,
            severity='info',
            details=log_details
        )

        return response


class TeamListView(RoleRequiredMixin, ListView):
    required_action = None
    model = Team
    template_name = "team_list.html"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Pobieranie aktywnej roli z sesji
        active_role = request.session.get('active_role', request.user.role)


        # Rola z pełnym dostępem do zarządzania zespołami (np. COO, HR, Admin)
        if Permission.verifyPermission(active_role, "can_manage_team"):
            self._restrict_to_own_teams = False
            return View.dispatch(self, request, *args, **kwargs)

        # Rola Manager - ograniczamy widok
        if active_role == "Manager":
            own_teams = Team.get_teams_managed_by(request.user)
            # Jeśli zarządza dokładnie jednym zespołem, przekierowujemy od razu do jego szczegółów
            if own_teams.count() == 1:
                return redirect("team-detail", pk=own_teams.first().pk)
            self._restrict_to_own_teams = True
            return View.dispatch(self, request, *args, **kwargs)

        return redirect("home")

    def get_queryset(self):
        # Pobieramy bazowy zestaw zespołów uwzględniając uprawnienia użytkownika
        if getattr(self, "_restrict_to_own_teams", False):
            return Team.get_teams_managed_by(self.request.user)
        return Team.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = self.get_queryset()

        # Podział bazowego querysetu na aktywne i nieaktywne zespoły dla szablonu
        context['active_teams'] = base_qs.filter(is_active=True)
        context['active_role'] = self.request.session.get('active_role', self.request.user.role)
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
DEFAULT_LEAVE_COLOR = '#2563eb'
ROLES_SEEING_MANAGERS = ('HR', 'COO', 'Admin')
PENDING_STATUSES = ('pending', 'PENDING', '1')
ACTIVE_STATUS_MARKERS = ('APPROV', 'PEND')
ACTIVE_STATUS_VALUES = ('1', '2', 'APPROVED', 'PENDING')
EMPLOYEE_FIELD = 'employee' if hasattr(LeaveRequest, 'employee') else 'user'


class TeamDetailView(DetailView):
    model = Team
    template_name = "team/team_detail.html"
    context_object_name = "team"

    def dispatch(self, request, *args, **kwargs):
        team = self.get_object()
        if not team.is_active:
            return redirect("team-list")
        return super().dispatch(request, *args, **kwargs)

    # -- Helpers ----------------------------------------------------------

    @staticmethod
    def _get_user_leave_stats(user):
        try:
            profile = user.worker_profile
        except WorkerProfile.DoesNotExist:
            return None, None
        try:
            total = profile._get_total_leave_days()
            available = profile.get_leave_days()
        except Exception:
            return None, None
        return available, total

    @staticmethod
    def _get_calendar_utils(d, cal_cache):
        cu = cal_cache.get(d.year)
        if cu is None:
            cu = Calendar_utils(d.year)
            cal_cache[d.year] = cu
        return cu

    @classmethod
    def _day_state(cls, d, cal_cache):
        cu = cls._get_calendar_utils(d, cal_cache)
        is_weekend = cu.is_weekend(d)
        return {
            'is_weekend': is_weekend,
            'is_non_working': is_weekend or cu.is_holiday(d),
        }

    @classmethod
    def _count_working_days(cls, start, end, cal_cache):
        total = 0
        current = start
        while current <= end:
            if not cls._day_state(current, cal_cache)['is_non_working']:
                total += 1
            current += timedelta(days=1)
        return total

    @staticmethod
    def _get_employee(leave):
        return getattr(leave, EMPLOYEE_FIELD, None)

    @staticmethod
    def _is_leave_active(leave):
        status = str(getattr(leave, 'status', '')).upper()
        return any(marker in status for marker in ACTIVE_STATUS_MARKERS) or status in ACTIVE_STATUS_VALUES

    @staticmethod
    def _is_leave_pending(leave):
        status = str(getattr(leave, 'status', '')).upper()
        return 'PEND' in status or status == '1'

    @staticmethod
    def _shift_month(year, month, delta):
        month += delta
        if month < 1:
            return year - 1, 12
        if month > 12:
            return year + 1, 1
        return year, month

    # -- Context ------------------------------------------------------------

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_role = self.request.session.get('active_role', getattr(self.request.user, 'role', ''))
        context["active_role"] = active_role

        # Flagi uprawnień dla przycisków (HR, COO, Admin)
        context["can_edit_team"] = active_role in ('HR', 'COO', 'Admin')
        context["can_deactivate"] = active_role in ('COO', 'Admin')

        context.update(self._build_calendar_context(active_role))
        return context

    def _get_target_month(self):
        today = date.today()
        try:
            year = int(self.request.GET.get('year', today.year))
            month = int(self.request.GET.get('month', today.month))
        except (ValueError, TypeError):
            year, month = today.year, today.month
        return today, year, month

    def _get_team_people(self, team, show_managers):
        """Zwraca (team_profiles, head_mgr, co_mgrs, all_users) - tylko aktywni użytkownicy."""
        team_profiles = list(
            WorkerProfile.objects.filter(team=team, user__is_active=True)
            .select_related('user')
            .order_by('user__last_name', 'user__first_name')
        )

        head_mgr = team.head_manager if (team.head_manager and team.head_manager.is_active) else None
        co_mgrs = [
            u for u in (team.co_managers.all() if hasattr(team, 'co_managers') else [])
            if u.is_active
        ]

        all_users = []
        if head_mgr:
            all_users.append(head_mgr)
        for cm in co_mgrs:
            if cm not in all_users:
                all_users.append(cm)
        for p in team_profiles:
            if p.user not in all_users:
                all_users.append(p.user)

        return team_profiles, head_mgr, co_mgrs, all_users

    def _assign_colors(self, all_users, manager_ids, show_managers):
        """Kolory/gwiazdki dla managerów tylko gdy rola je widzi (HR/COO/Admin);
        manager przeglądający własny zespół ich nie dostaje."""
        user_colors = {}
        color_i = 0
        for u in all_users:
            if u.id in manager_ids and not show_managers:
                continue
            user_colors[u.id] = COLOR_PALETTE[color_i % len(COLOR_PALETTE)]
            color_i += 1
        return user_colors

    def _build_calendar_context(self, active_role):
        today, year, month = self._get_target_month()
        team = self.object
        cal_cache = {}
        show_managers = active_role in ROLES_SEEING_MANAGERS

        team_profiles, head_mgr, co_mgrs, all_users = self._get_team_people(team, show_managers)
        manager_ids = {u.id for u in ([head_mgr] + co_mgrs) if u}
        user_colors = self._assign_colors(all_users, manager_ids, show_managers)

        pending_counts = {u.id: 0 for u in all_users}
        pending_qs = LeaveRequest.objects.filter(
            **{f'{EMPLOYEE_FIELD}_id__in': pending_counts.keys()},
            status__in=PENDING_STATUSES,
        )
        for leave in pending_qs:
            pending_counts[getattr(leave, f'{EMPLOYEE_FIELD}_id')] += 1

        head_manager_info = None
        if head_mgr:
            avail, total = self._get_user_leave_stats(head_mgr)
            head_manager_info = {
                'user': head_mgr,
                'color': user_colors.get(head_mgr.id),
                'leave_available': avail,
                'leave_total': total,
                'can_highlight': show_managers,
                'pending_count': pending_counts.get(head_mgr.id, 0),
            }

        co_managers_info = [
            {
                'user': cm,
                'color': user_colors.get(cm.id),
                'leave_available': avail,
                'leave_total': total,
                'can_highlight': show_managers,
                'pending_count': pending_counts.get(cm.id, 0),
            }
            for cm in co_mgrs
            for avail, total in [self._get_user_leave_stats(cm)]
        ]

        members_info = [
            {
                'profile': p,
                'color': user_colors.get(p.user.id, DEFAULT_MEMBER_COLOR),
                'leave_available': avail,
                'leave_total': total,
                'pending_count': pending_counts.get(p.user.id, 0),
            }
            for p in team_profiles
            for avail, total in [self._get_user_leave_stats(p.user)]
        ]

        # --- Siatka miesiąca: pełne tygodnie, łącznie z dniami sąsiednich miesięcy ---
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdatescalendar(year, month)
        display_start = month_days[0][0]
        display_end = month_days[-1][-1]

        visible_user_ids = list(user_colors.keys())
        leaves_qs = LeaveRequest.objects.filter(
            **{f'{EMPLOYEE_FIELD}_id__in': visible_user_ids},
            start_date__lte=display_end,
            end_date__gte=display_start,
        ).select_related(EMPLOYEE_FIELD).order_by('start_date', '-amount_days')

        valid_leaves = [l for l in leaves_qs if self._is_leave_active(l)]

        # Dni robocze CAŁEGO wniosku (bez weekendów/świąt), liczone raz na wniosek
        leave_working_days = {
            l.id: self._count_working_days(l.start_date, l.end_date, cal_cache)
            for l in valid_leaves
        }

        calendar_weeks = [
            self._build_week(
                week_dates, month, today, valid_leaves, display_start, display_end,
                user_colors, manager_ids, show_managers, leave_working_days, cal_cache,
            )
            for week_dates in month_days
        ]

        prev_year, prev_month = self._shift_month(year, month, -1)
        next_year, next_month = self._shift_month(year, month, 1)

        return {
            'calendar_year': year,
            'calendar_month': month,
            'calendar_month_name': PL_MONTHS[month],
            'calendar_weeks': calendar_weeks,
            'members_info': members_info,
            'head_manager_info': head_manager_info,
            'co_managers_info': co_managers_info,
            'show_managers_on_calendar': show_managers,
            'calendar_prev_year': prev_year,
            'calendar_prev_month': prev_month,
            'calendar_next_year': next_year,
            'calendar_next_month': next_month,
        }

    def _build_week(self, week_dates, month, today, valid_leaves, display_start, display_end,
                     user_colors, manager_ids, show_managers, leave_working_days, cal_cache):
        week_start = week_dates[0]
        week_end = week_dates[-1]

        days_headers = [
            {
                'day': d.day,
                'is_today': d == today,
                'is_current_month': d.month == month,
                'is_non_working': self._day_state(d, cal_cache)['is_non_working'],
            }
            for d in week_dates
        ]

        lanes_data = []
        for leave in valid_leaves:
            emp = self._get_employee(leave)
            if not emp:
                continue
            if emp.id in manager_ids and not show_managers:
                continue

            render_start = max(leave.start_date, display_start)
            render_end = min(leave.end_date, display_end)
            if render_start > week_end or render_end < week_start:
                continue

            start_col = max(1, (render_start - week_start).days + 1)
            end_col = min(7, (render_end - week_start).days + 1)
            span = end_col - start_col + 1

            day_states = [
                self._day_state(week_start + timedelta(days=col - 1), cal_cache)
                for col in range(start_col, end_col + 1)
            ]

            lanes_data.append({
                'leave_id': leave.id,
                'owner_id': emp.id,
                'name': emp.get_full_name() or emp.username,
                'is_manager': emp.id in manager_ids,
                'color': user_colors.get(emp.id, DEFAULT_LEAVE_COLOR),
                'is_pending': self._is_leave_pending(leave),
                'grid_column_start': start_col,
                'grid_column_span': span,
                'has_prev': leave.start_date < display_start and render_start >= week_start,
                'has_next': leave.end_date > display_end and render_end <= week_end,
                'sharp_left': leave.start_date < week_start,
                'sharp_right': leave.end_date > week_end,
                'show_label': week_start <= render_start <= week_end,
                'day_states': day_states,
                'working_days': leave_working_days.get(leave.id, 0),
                'grid_normal': ' '.join(['1fr'] * span),
                'grid_hidden': ' '.join('0px' if ds['is_weekend'] else '1fr' for ds in day_states),
            })

        self._pack_lanes(lanes_data)

        return {
            'days_headers': days_headers,
            'lanes': lanes_data,
        }

    @staticmethod
    def _pack_lanes(lanes_data):
        """Track packing: przydziela każdemu paskowi urlopu najniższy wolny wiersz,
        usuwając puste luki między wnioskami w gridzie."""
        lanes_data.sort(key=lambda x: (x['grid_column_start'], -x['grid_column_span']))

        tracks = []
        for lane in lanes_data:
            l_start = lane['grid_column_start']
            l_end = l_start + lane['grid_column_span'] - 1

            for i, track in enumerate(tracks):
                overlap = any(
                    l_start <= (e['grid_column_start'] + e['grid_column_span'] - 1)
                    and l_end >= e['grid_column_start']
                    for e in track
                )
                if not overlap:
                    track.append(lane)
                    lane['track'] = i + 1
                    break
            else:
                tracks.append([lane])
                lane['track'] = len(tracks)

class TeamCreateView(WarningMixin, RoleRequiredMixin, CreateView):
    required_action = "can_manage_team"
    model = Team
    form_class = TeamForm
    template_name = "team/team_form.html"
    success_url = reverse_lazy("team-list")


class TeamUpdateView(WarningMixin, RoleRequiredMixin, UpdateView):
    required_action = "can_manage_team"
    model = Team
    form_class = TeamForm
    template_name = "team/team_form.html"
    success_url = reverse_lazy("team-list")

    def get_queryset(self):
        return Team.objects.filter(is_active=True)


class TeamDeleteView(RoleRequiredMixin, DeleteView):
    required_action = "can_manage_team"
    model = Team
    template_name = "team/team_confirm_delete.html"
    success_url = reverse_lazy("team-list")

    def get_queryset(self):
        return Team.objects.filter(is_active=True)

    def form_valid(self, form):
        team = self.get_object()
        team_name = team.name
        team_id = team.pk
        team.soft_delete()

        ActivityLog.objects.create(
            who=self.request.user,
            action='delete',
            object_type='team',
            object_id=team_id,
            severity='warning',
            details=f"Dezaktywowano zespół '{team_name}'."
        )

        messages.success(self.request, f"Zespół '{team_name}' został pomyślnie dezaktywowany.")
        return redirect(self.success_url)

class TeamMembersUpdateView(RoleRequiredMixin, FormView):
    required_action = "can_manage_team"
    form_class = TeamMembersForm
    template_name = "team/team_members_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.team = get_object_or_404(Team, pk=kwargs["pk"], is_active=True)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["team"] = self.team
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["team"] = self.team
        return context

    def form_valid(self, form):
        form.save()

        log_details = form.generate_log_details()
        ActivityLog.objects.create(
            who=self.request.user,
            action='update',
            object_type='team',
            object_id=self.team.pk,
            severity='info',
            details=log_details
        )

        messages.success(self.request, f"Pomyślnie zaktualizowano skład zespołu {self.team.name}.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("team-detail", kwargs={"pk": self.team.pk})