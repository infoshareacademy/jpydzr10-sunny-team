from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from leaves.models import LeaveRequest
from logs.models import ChangeLog

# Słownik
STATUS_TO_ACTION = {
    LeaveRequest.Status.APPROVED: 'zatwierdz',
    LeaveRequest.Status.REJECTED: 'odrzuc',
    LeaveRequest.Status.CANCELED: 'anuluj',
}

# Sygnał PRE-SAVE: Wywołuje się przed zapisaniem obiektu w bazie danych
@receiver(pre_save, sender=LeaveRequest)
def remember_old_status(sender, instance, **kwargs):
    # Sprawdzamy, czy obiekt ma już klucz główny (PK) – czyli czy istnieje w bazie
    if instance.pk:
        try:
            # Pobieramy aktualny stan obiektu prosto z bazy danych, zanim nadpiszemy go nowymi danymi
            old = LeaveRequest.objects.get(pk=instance.pk)
            # Zapisujemy stary status w tymczasowym polu dynamicznym `_old_status` w pamięci obiektu
            instance._old_status = old.status
        # Zabezpieczenie na wypadek, gdyby obiekt miał PK, ale fizycznie nie było go w bazie
        except LeaveRequest.DoesNotExist:
            instance._old_status = None
    else:
        # Jeśli obiekt nie ma PK, oznacza to, że jest to zupełnie nowy wniosek
        instance._old_status = None

# Sygnał POST-SAVE: Wywołuje się natychmiast po udanym zapisaniu obiektu w bazie danych
@receiver(post_save, sender=LeaveRequest)
def log_leave_request_change(sender, instance, created, **kwargs):
    # Obiekt został właśnie utworzony
    if created:
        ChangeLog.objects.create(
            who=instance.employee,
            action='dodaj',
            object_type='leave_request',
        )
        return

    # Pobieramy stary status zapamiętany w pre_save (jeśli nie istnieje, domyślnie None) i pobieramy nowy w new_status
    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status

    # Wniosek był oczekujący i nadal pozostał oczekujący (np. zmiana daty)
    if old_status == new_status == LeaveRequest.Status.PENDING:
        ChangeLog.objects.create(
            who=instance.employee,
            action='edytuj',
            object_type='leave_request',
        )
        return

    # Nastąpiła zmiana statusu wniosku (np. z oczekującego na zatwierdzony)
    if old_status != new_status:
        # Pobieramy odpowiednią nazwę akcji ze słownika na podstawie nowego statusu
        action = STATUS_TO_ACTION.get(new_status)
        # Jeśli nowy status nie jest uwzględniony w słowniku, ignorujemy logowanie
        if action is None:
            return

        # Jeśli pole `who_confirmed` jest uzupełnione, to on jest autorem logu.
        # W przeciwnym razie przyjmujemy, że zmiany dokonał sam pracownik.
        who = instance.who_confirmed if instance.who_confirmed else instance.employee

        # Tworzymy końcowy log o zmianie statusu
        ChangeLog.objects.create(
            who=who,
            action=action,
            object_type='leave_request',
        )