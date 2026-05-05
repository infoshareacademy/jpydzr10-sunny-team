from django.contrib.auth.models import AbstractUser
from django.db import models

<<<<<<< JPY101-48-Szkielet-dashboardu-z-kartami
# Create your models here.
=======
>>>>>>> main

class User(AbstractUser):
    ROLES = [
        ('Admin', 'Admin'),
        ('Manager', 'Manager'),
        ('HR', 'HR'),
        ('Worker', 'Worker'),
    ]
    role = models.CharField(max_length=20, choices=ROLES, null=True, blank=True)