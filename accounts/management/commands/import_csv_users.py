import csv
import os
from django.core.management.base import BaseCommand
from accounts.models import User
from leaves.models import WorkerProfile


class Command(BaseCommand):
    help = 'Importuje użytkowników z pliku CSV'

    def handle(self, *args, **options):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        users_file = os.path.join(base_dir, 'startup', 'users.csv')
        users_map = {}

        with open(users_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                users_map[row['user_id']] = row['username']
                user, created = User.objects.get_or_create(
                username=row['username'],
                defaults={'is_active':row['is_active'],'role':row['role']})
                if created:
                    user.set_unusable_password()
                    user.save()
                    self.stdout.write(f'Utworzono: {user.username}, rola {user.role}')
                else:
                    self.stdout.write(f'Już istnieje: {user.username}, rola {user.role}')
        

        workers_file = os.path.join(base_dir,'startup','workers.csv')
        with open(workers_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                username = users_map[row['user_id']] 
                profile, created = WorkerProfile.objects.get_or_create(
                user=User.objects.get(username=username),
                defaults={"hire_date":row['hire_date'],"team":row['team'], 
                          "other_experience_years":row['other_experience_years'],
                          "used_leave_days":row['used_leave_days'],
                          "other_experience_days":row['other_experience_days']})
                if created:
                    self.stdout.write(f'Utworzono profil: {username}')
                else:
                    self.stdout.write(f'Profil już istnieje: {username}')