from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

class Team(models.Model):
    name = models.CharField(
        max_length=100, unique=True, verbose_name="Nazwa zespołu"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Opis zespołu",
        help_text="Opcjonalny opis zakresu działań zespołu",
    )
    head_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="head_managed_teams",
        verbose_name="Główny manager",
    )
    co_managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="co_managed_teams",
        verbose_name="Współzarządzający",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Data utworzenia"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktywny",
        help_text="Czy zespół jest aktywny. Odznaczenie oznacza miękkie usunięcie."
    )

    class Meta:
        verbose_name = "Zespół"
        verbose_name_plural = "Zespoły"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def add_co_manager(self, user):
        with transaction.atomic():
            self.co_managers.add(user)

    def remove_co_manager(self, user):
        with transaction.atomic():
            self.co_managers.remove(user)

    def set_co_managers(self, users):
        with transaction.atomic():
            self.co_managers.set(users)

    @property
    def members_count(self) -> int:
        return self.members.filter(user__is_active=True).count()

    @property
    def managers_count(self) -> int:
        count = self.co_managers.count()
        if self.head_manager_id:
            count += 1
        return count

    def get_members(self):
        return self.members.all()

    def get_all_managers(self):
        managers = list(self.co_managers.all())
        if self.head_manager:
            managers.insert(0, self.head_manager)
        return managers

    def soft_delete(self):
        """Miękkie usunięcie zespołu - dezaktywacja i odpięcie członków."""
        from leaves.models import WorkerProfile
        with transaction.atomic():
            self.is_active = False
            self.head_manager = None
            self.save()
            self.co_managers.clear()
            WorkerProfile.objects.filter(team=self).update(team=None)

    def clean(self):
        super().clean()
        if self.pk:
            if not self.head_manager_id and self.co_managers.exists():
                raise ValidationError({
                    "head_manager": "Nie można usunąć Głównego Managera, dopóki zespół "
                                    "posiada Współzarządzających (Co-Managers)!"
                })
            if self.head_manager_id and self.co_managers.filter(pk=self.head_manager_id).exists():
                raise ValidationError({
                    "co_managers": "Główny Manager nie może znajdować się na liście Współzarządzających."
                })


    def save(self, *args, **kwargs):
        self.full_clean(exclude=["co_managers"] if self.pk is None else None)
        super().save(*args, **kwargs)

    @staticmethod
    def get_teams_managed_by(user):
        """Wszystkie zespoły, w których user jest head_managerem lub co-managerem."""
        return Team.objects.filter(
            Q(head_manager=user) | Q(co_managers=user)
        ).distinct()


@receiver(m2m_changed, sender=Team.co_managers.through)
def validate_co_managers(sender, instance, action, pk_set, **kwargs):
    if action == "pre_add" and instance.head_manager_id and pk_set:
        if instance.head_manager_id in pk_set:
            raise ValidationError(
                "Głównego Managera nie można dodać jako Co-Managera tego samego zespołu."
            )

    if action in ("post_add", "post_remove", "post_clear"):
        if not instance.head_manager_id and instance.co_managers.exists():
            raise ValidationError(
                "Zespół nie może posiadać Co-Managerów bez przypisanego Głównego Managera."
            )