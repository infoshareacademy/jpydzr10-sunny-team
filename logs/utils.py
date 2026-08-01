from django.utils import timezone
from datetime import timedelta
from logs.models import AuthLog
from django.contrib.auth import get_user_model

User = get_user_model()


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 5
FAILED_ACTIONS = ['login_failed', 'incorrect_username']


def get_lockout_until(ip_address):
    """
    Zwraca datetime, do kiedy trwa blokada danego IP, albo None jeśli brak blokady.
    Blokada trwa LOCKOUT_WINDOW_MINUTES od najstarszej z ostatnich MAX_FAILED_ATTEMPTS
    nieudanych prób (tak, żeby okno "zjeżdżało" wraz z kolejnymi próbami).
    """
    since = timezone.now() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
    recent_failed = list(
        AuthLog.objects.filter(
            ip_address=ip_address,
            action__in=FAILED_ACTIONS,
            invalidated=False,
            timestamp__gte=since,
        ).order_by('-timestamp')[:MAX_FAILED_ATTEMPTS]
    )
    if len(recent_failed) < MAX_FAILED_ATTEMPTS:
        return None
    oldest_of_recent = recent_failed[-1].timestamp
    lockout_until = oldest_of_recent + timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
    if lockout_until <= timezone.now():
        return None
    return timezone.localtime(lockout_until)


def count_failed_attempts(ip_address):
    """Liczba nieinwalidowanych nieudanych prób z danego IP w oknie czasowym (przed dodaniem nowej)."""
    since = timezone.now() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
    return AuthLog.objects.filter(
        ip_address=ip_address,
        action__in=FAILED_ACTIONS ,
        invalidated=False,
        timestamp__gte=since,
    ).count()


def reset_failed_attempts(ip_address):
    """
    Oznacza dotychczasowe nieudane proby (z danego IP) jako 'invalidated' po udanym zalogowaniu.
    Historia zostaje w bazie, ale nie liczy sie juz do lockout.
    """
    AuthLog.objects.filter(
        ip_address=ip_address,
        action__in=FAILED_ACTIONS + ['ip_locked', '2fa_failed'],
        invalidated=False,
    ).update(invalidated=True)


def log_failed_attempt(user, raw_username, ip_address):
    attempt_no = count_failed_attempts(ip_address) + 1
    if user is None:
        action = 'incorrect_username'
        details = (
            f"Logowanie na nieistniejący username: {raw_username}. "
            f"Próba {attempt_no}/{MAX_FAILED_ATTEMPTS} przed blokadą."
        )
    else:
        action = 'login_failed'
        details = f"Próba {attempt_no}/{MAX_FAILED_ATTEMPTS} przed blokadą."

    AuthLog.objects.create(
        user=user,
        ip_address=ip_address,
        action=action,
        severity='warning',
        details=details,
    )

    if attempt_no >= MAX_FAILED_ATTEMPTS:
        lockout_until = get_lockout_until(ip_address)
        if lockout_until is not None:
            readable_date = lockout_until.strftime("%d-%m-%Y %H:%M:%S")
            AuthLog.objects.create(
                user=user,
                ip_address=ip_address,
                action='ip_locked',
                severity='critical',
                details=f'Zablokowane do {readable_date}',
            )
        return lockout_until
    return None