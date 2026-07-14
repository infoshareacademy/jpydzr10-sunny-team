from django.db import models
from django.conf import settings


class ActivityLog(models.Model):
    """Logi zmian obiektów biznesowych (głównie wnioski urlopowe, użytkownicy)."""
    ACTION_CHOICES = [
        ('create', 'Dodaj'),
        ('update', 'Edytuj'),
        ('approve', 'Zatwierdź'),
        ('reject', 'Odrzuć'),
        ('cancel', 'Anuluj'),
        ('delete', 'Usuń'),
        ('password_reset', 'Reset hasła'),
        ('new_account', 'Nowe Konto'),
        ('role_change', 'Zmiana roli'),
    ]
    OBJECT_TYPE_CHOICES = [
        ('user', 'Użytkownik'),
        ('leave_request', 'Wniosek urlopowy'),
        ('system_settings', 'Ustawienia systemu'),
    ]
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Ostrzeżenie'),
        ('critical', 'Krytyczne'),
    ]
    who = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=20, choices=OBJECT_TYPE_CHOICES)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='info')
    details = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['object_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.who} - {self.action} - {self.object_type}#{self.object_id} - {self.created_at}"


class AuthLog(models.Model):
    """Logi dotyczące autoryzacji i bezpieczeństwa (logowania, dostęp)."""

    ACTION_CHOICES = [
        ('login_success', 'Logowanie udane'),
        ('login_failed', 'Logowanie nieudane'),
        ('logout', 'Wylogowanie'),
        ('access_denied_403', 'Odmowa dostępu'),
        ('ip_locked', 'IP zablokowane'),
    ]

    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Ostrzeżenie'),
        ('critical', 'Krytyczne'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auth_logs',
    )
    username = models.CharField(max_length=150, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='info')
    invalidated = models.BooleanField(default=False)
    details = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['username', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['ip_address', 'action', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.username} - {self.action} - {self.ip_address} - {self.timestamp}"