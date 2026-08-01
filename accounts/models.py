from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLES = [
        ('Admin', 'Admin'),
        ('COO', 'COO'),
        ('HR', 'HR'),
        ('Manager', 'Manager'),
        ('Worker', 'Worker'),
    ]
    role = models.CharField(max_length=20, choices=ROLES, null=True, blank=True)

    must_change_password = models.BooleanField(
        default=True,
        verbose_name="Musi zmienić hasło przy pierwszym logowaniu",
    )