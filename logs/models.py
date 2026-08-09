from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid
from django.utils import timezone
from datetime import timedelta


class ActivityLog(models.Model):
    """Logi zmian obiektów biznesowych (głównie wnioski urlopowe, użytkownicy)."""

    ACTION_CHOICES = [
        ('create', _('Dodaj')),
        ('update', _('Edytuj')),
        ('delete', _('Usuń')),
        ('approve', _('Zatwierdź')),
        ('reject', _('Odrzuć')),
        ('cancel', _('Anuluj')),
    ]

    OBJECT_TYPE_CHOICES = [
        ('user', _('Konto Użytkownika')),
        ('worker_profile', _('Profil Pracownika')),
        ('team', _('Zespół')),
        ('leave_request', _('Wniosek urlopowy')),
    ]

    SEVERITY_CHOICES = [
        ('info', _('Info')),
        ('warning', _('Ostrzeżenie')),
        ('critical', _('Krytyczne')),
    ]

    who = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs',
        verbose_name=_('Użytkownik'),
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name=_('Akcja'),
    )
    object_type = models.CharField(
        max_length=20,
        choices=OBJECT_TYPE_CHOICES,
        verbose_name=_('Typ obiektu'),
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('ID obiektu'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Data utworzenia'),
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='info',
        verbose_name=_('Waga'),
    )
    details = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Szczegóły'),
    )

    class Meta:
        verbose_name = _('Log aktywności')
        verbose_name_plural = _('Logi aktywności')
        indexes = [
            models.Index(fields=['object_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.who} - {self.get_action_display()} - {self.get_object_type_display()}#{self.object_id} - {self.created_at}"


class AuthLog(models.Model):
    """Logi dotyczące autoryzacji i bezpieczeństwa (logowania, dostęp)."""

    ACTION_CHOICES = [
        ('login_success', _('Logowanie udane')),
        ('login_failed', _('Logowanie nieudane')),
        ('incorrect_username', _('Brak użytkownika')),
        ('2fa_success', _('Weryfikacja 2FA udana')),
        ('2fa_failed', _('Niepoprawny kod 2FA')),
        ('logout', _('Wylogowanie')),
        ('access_denied_403', _('Odmowa dostępu')),
        ('ip_locked', _('IP zablokowane')),
        ('role_change', _('Zmiana roli')),
        ('password_changed', _('Zmiana hasła')),
    ]

    SEVERITY_CHOICES = [
        ('info', _('Info')),
        ('warning', _('Ostrzeżenie')),
        ('critical', _('Krytyczne')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auth_logs',
        verbose_name=_('Użytkownik'),
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('Adres IP'),
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Data i godzina'),
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name=_('Akcja'),
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='info',
        verbose_name=_('Waga'),
    )
    invalidated = models.BooleanField(
        default=False,
        verbose_name=_('Unieważniony'),
    )
    details = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Szczegóły'),
    )

    class Meta:
        verbose_name = _('Log autoryzacji')
        verbose_name_plural = _('Logi autoryzacji')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['ip_address', 'action', 'timestamp']),
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
