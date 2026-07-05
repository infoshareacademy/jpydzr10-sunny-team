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
        ('reset_hasla','Reset_hasla'),
        ('login','Login'),
        ('logout', 'Logout'),
        ('login_failed','Login_failed'),
        ('403','Forbidden_403'),
        ('switch_choice','Switch_choice'),

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
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical')
    ]

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=20,choices=OBJECT_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    severity = models.CharField(max_length=10,choices=SEVERITY_CHOICES,default='info')
    details = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.who} - {self.action} - {self.object_type} - {self.created_at} - {self.ip_address} -  "