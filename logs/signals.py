from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext as _

from leaves.models import LeaveRequest
from logs.models import ActivityLog

# Słownik
STATUS_TO_ACTION = {
    LeaveRequest.Status.APPROVED: 'approve',
    LeaveRequest.Status.REJECTED: 'reject',
    LeaveRequest.Status.CANCELED: 'cancel',
}

# Sygnał PRE-SAVE: Wywołuje się przed zapisaniem obiektu w bazie danych
@receiver(pre_save, sender=LeaveRequest)
def remember_old_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = LeaveRequest.objects.get(pk=instance.pk)
            instance._old_status = old.status
        except LeaveRequest.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=LeaveRequest)
def log_leave_request_change(sender, instance, created, **kwargs):
    if created:
        ActivityLog.objects.create(
            who=instance.employee,
            action='create',
            object_type='leave_request',
            object_id=instance.id,
            details=_("Złożono wniosek: %(start)s – %(end)s")
            % {'start': instance.start_date, 'end': instance.end_date},
        )
        return

    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status

    if old_status == new_status == LeaveRequest.Status.PENDING:
        ActivityLog.objects.create(
            who=instance.employee,
            action='update',
            object_type='leave_request',
            object_id=instance.id,
            details=_("Zmieniono wniosek: %(start)s – %(end)s")
            % {'start': instance.start_date, 'end': instance.end_date},
        )
        return

    if old_status != new_status:
        action = STATUS_TO_ACTION.get(new_status)
        if action is None:
            return

        who = instance.who_confirmed if instance.who_confirmed else instance.employee

        ActivityLog.objects.create(
            who=who,
            action=action,
            object_type='leave_request',
            object_id=instance.id,
            details=_("Zmieniono status wniosku na %(status)s")
            % {'status': instance.get_status_display()},
        )