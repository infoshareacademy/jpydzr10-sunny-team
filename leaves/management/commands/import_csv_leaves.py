import csv
import os
from django.core.management.base import BaseCommand
from leaves.model_leave_request import LeaveRequest
from accounts.models import User

class Command(BaseCommand):
    help = 'Importuje urlopy z pliku CSV'

    def handle(self, *args, **options):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        users_file = os.path.join(base_dir, 'startup', 'users.csv')
        users_map = {}

        with open(users_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                users_map[row['user_id']] = row['username']

        leave_file = os.path.join(base_dir,'startup','leave_requests.csv')
        with open(leave_file,'r',encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                username = users_map[row['employee_id']]
                employee = User.objects.get(username=username)
                if not LeaveRequest.objects.filter(employee=employee, start_date=row['start_date'],
                                                   end_date=row['end_date']).exists():
                    LeaveRequest.objects.bulk_create([LeaveRequest(
                        employee=employee,
                        start_date=row['start_date'],
                        end_date=row['end_date'],
                        amount_days=row['days'],
                        status=row['status'],
                    )])
                    self.stdout.write(f"Utworzono wniosek dla: {username}")
                else:
                    self.stdout.write(f"Wniosek już istnieje dla: {username}")