from django.db import models
from django.conf import settings
import uuid
from django.utils import timezone
from datetime import timedelta


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

class LoginAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_attempts',
    )
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    invalidated = models.BooleanField(
        default=False,
        help_text="True gdy ten nieudany login zostal 'wyzerowany' przez pozniejsze udane logowanie."
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['username', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]

    def __str__(self):
        status = 'OK' if self.success else 'FAIL'
        return f"{self.username} - {status} - {self.ip_address} - {self.timestamp}"
class EmailVerificationCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

class PasswordResetToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=24)

    def __str__(self):
        return f"{self.user} - {self.token} - {self.created_at}"