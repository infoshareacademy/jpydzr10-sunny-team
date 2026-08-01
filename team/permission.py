from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

from logs.models import AuthLog
from logs.utils import get_client_ip
from accounts.permission import Permission


class TeamDetailAccessMixin(LoginRequiredMixin):
    """
    Dostęp do wglądu zespołu:
    - użytkownicy z 'can_manage_team' (Admin/COO/HR)
    - head_manager i co_managers TEGO zespołu
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        active_role = request.session.get('active_role', request.user.role)

        if Permission.verifyPermission(active_role, "can_manage_team"):
            return super().dispatch(request, *args, **kwargs)

        team = self.get_object()
        is_team_leader = (
            team.head_manager_id == request.user.pk
            or team.co_managers.filter(pk=request.user.pk).exists()
        )

        if is_team_leader:
            return super().dispatch(request, *args, **kwargs)

        AuthLog.objects.create(
            user=request.user,
            action='access_denied_403',
            details=f'Brak dostępu do zespołu {team.pk}. Aktywna rola: {active_role}',
            ip_address=get_client_ip(request),
            severity='warning'
        )
        return redirect('home')