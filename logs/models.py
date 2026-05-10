from django.db import models
from django.conf import settings


class ChangeLog(models.Model):
    ACTION_CHOICES = [
        ('dodaj','Dodaj'),
        ('usun', 'Usun'),
        ('edytuj', 'Edytuj'),
        ('zatwierdz', 'Zatwierdz'),
        ('odrzuc', 'Odrzuc'),
        ('anuluj','Anuluj'),
        ('reset_hasla','Reset_hasla')
    ]

    OBJECT_TYPE_CHOICES = [
        ('user','User'),
        ('leave_request','Leave_request'),
        ('password','Password')
    ]
    who = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=20,choices=OBJECT_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.who} - {self.action} - {self.object_type} - {self.created_at} "