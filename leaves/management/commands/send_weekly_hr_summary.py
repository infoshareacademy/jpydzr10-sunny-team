from django.core.management.base import BaseCommand, CommandError
from leaves.models import WorkerProfile, LeaveRequest
from accounts.models import User

class Command(BaseCommand):
    help = "Wysyłka cotygodniowych podsumowań dla HR"

    def handle(self, *args, **options):
        hr_users = User.objects.filter(role='HR')
        all_hr = hr_users.all()

        from datetime import date, timedelta
        tydzien_temu = date.today() - timedelta(days=7)
        wnioski = LeaveRequest.objects.filter(created_at__date__gte=tydzien_temu)
        for hr in all_hr:
            try:
                profil = WorkerProfile.objects.get(user=hr)
                team = profil.team
            except WorkerProfile.DoesNotExist:
                continue

            self.stdout.write(f"\n=== Podsumowanie dla HR: {hr.first_name} {hr.last_name} (team: {team}) ===")

            team_profiles = WorkerProfile.objects.filter(team=team)
            team_user_ids = team_profiles.values_list('user', flat=True)
            wnioski_teamu = wnioski.filter(employee__in=team_user_ids)

            if not wnioski_teamu.exists():
                self.stdout.write("  Brak wniosków w tym tygodniu.")
            else:
                for wniosek in wnioski_teamu:
                    self.stdout.write(f"  - {wniosek}")

