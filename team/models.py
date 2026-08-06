from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class TeamQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def archived(self):
        return self.filter(is_active=False)

    def for_user(self, user):
        """
        Zwraca zespoły, w których dany użytkownik pełni rolę Managera lub HR.
        Admin widzi wszystkie zespoły.
        """
        if not user or not user.is_authenticated:
            return self.none()

        role = getattr(user, "role", None)
        if role == "Manager":
            return self.filter(manager=user)
        elif role == "HR":
            return self.filter(hr=user)
        elif role == "Admin":
            return self.all()

        return self.filter(models.Q(manager=user) | models.Q(hr=user)).distinct()

    def manageable_by(self, user, active_role=None):
        """
        Zespoły, których wnioski urlopowe użytkownik może przeglądać i akceptować:
        - Admin: wszystkie zespoły
        - Manager: swoje zespoły (zawsze)
        - HR: zespoły, w których jest przypisany jako HR, gdy:
            a) zespół nie ma przypisanego managera, LUB
            b) manager tego zespołu jest AKTUALNIE na zaakceptowanym urlopie
        """
        from leaves.models import LeaveRequest

        if not user or not user.is_authenticated:
            return self.none()

        role = active_role or getattr(user, "role", None)
        today = date.today()

        if role == "Admin":
            return self.all()

        if role == "Manager":
            return self.filter(manager=user)

        if role == "HR":
            manager_on_approved_leave = LeaveRequest.objects.filter(
                employee_id=models.OuterRef("manager_id"),
                status=LeaveRequest.Status.APPROVED,
                start_date__lte=today,
                end_date__gte=today,
            )
            return self.filter(hr=user).filter(
                models.Q(manager__isnull=True) | models.Exists(manager_on_approved_leave)
            )

        return self.none()


class TeamManager(models.Manager):
    def get_queryset(self):
        return TeamQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def archived(self):
        return self.get_queryset().archived()

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def manageable_by(self, user, active_role=None):
        return self.get_queryset().manageable_by(user, active_role=active_role)

    def get_team_ids_for_user(self, user) -> list[int]:
        """Zwraca płaską listę ID zespołów przypisanych do użytkownika."""
        return list(self.for_user(user).values_list("id", flat=True))


class Team(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nazwa zespołu"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Opis zespołu"
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_team",
        verbose_name="Manager zespołu",
    )
    hr = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_team",
        verbose_name="Opiekun HR",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Czy aktywny"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data utworzenia"
    )

    objects = TeamManager()

    class Meta:
        ordering = ["name"]
        verbose_name = "Zespół"
        verbose_name_plural = "Zespoły"

    def __str__(self) -> str:
        status = "" if self.is_active else " (Archiwum)"
        return f"{self.name}{status}"

    @property
    def members_count(self) -> int:
        """Zwraca liczbę aktywnych pracowników obecnie przypisanych do zespołu."""
        return self.members.filter(user__is_active=True).count()

    def clean(self):
        super().clean()
        errors = {}

        #  Sprawdzanie obecności Managera i HR dla aktywnego zespołu z członkami
        if self.pk and self.is_active and self.members_count > 0:
            if not self.manager_id:
                errors["manager"] = "Zespół posiada pracowników – przypisanie Managera jest wymagane."
            if not self.hr_id:
                errors["hr"] = "Zespół posiada pracowników – przypisanie HR jest wymagane."

        #  Walidacja: Manager nie może należeć do tego zespołu jako pracownik
        if self.manager_id and hasattr(self.manager, "worker_profile") and self.manager.worker_profile.team_id:
            if self.pk and self.manager.worker_profile.team_id == self.pk:
                errors["manager"] = (
                    f"Wskazany Manager ({self.manager.get_full_name() or self.manager.username}) "
                    f"jest członkiem tego zespołu. Manager musi należeć do innego zespołu."
                )

        #  Walidacja: HR nie może należeć do tego zespołu jako pracownik
        if self.hr_id and hasattr(self.hr, "worker_profile") and self.hr.worker_profile.team_id:
            if self.pk and self.hr.worker_profile.team_id == self.pk:
                errors["hr"] = (
                    f"Wskazana osoba z HR ({self.hr.get_full_name() or self.hr.username}) "
                    f"jest członkiem tego zespołu. HR musi należeć do innego zespołu."
                )

        if errors:
            raise ValidationError(errors)

    def soft_delete(self):
        """Dezaktywuje zespół i odpina aktualnych członków oraz kierownictwo."""
        from leaves.models import WorkerProfile

        with transaction.atomic():
            WorkerProfile.objects.filter(team=self).update(team=None)
            self.manager = None
            self.hr = None
            self.is_active = False
            self.save()

    @classmethod
    def get_teams_managed_by(cls, user):
        if not user or not user.is_authenticated:
            return cls.objects.none()
        return cls.objects.filter(
            models.Q(manager=user) | models.Q(hr=user)
        ).distinct()