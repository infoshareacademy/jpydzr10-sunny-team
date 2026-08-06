from dateutil.relativedelta import relativedelta
from team.models import Team
from django.db import models
from django.conf import settings
from datetime import date


class WorkerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="worker_profile",
        verbose_name="Profil pracownika"
    )

    team = models.ForeignKey(
        "team.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
        verbose_name="Aktualny zespół"
    )

    hire_date = models.DateField(verbose_name="Data zatrudnienia")
    other_experience_years = models.IntegerField(default=0, verbose_name="Wcześniejsze doświadczenie (lata)")
    other_experience_days = models.IntegerField(default=0, verbose_name="Wcześniejsze doświadczenie (dni)")
    used_leave_days = models.IntegerField(default=0, verbose_name="Wykorzystane dni urlopu")

    class Meta:
        verbose_name = "Profil pracownika"
        verbose_name_plural = "Profile pracowników"

    def __str__(self):
        team_str = self.team.name if self.team else "Brak zespołu"
        return f"Profil: {self.user.get_full_name() or self.user.username} ({team_str})"


    def _total_experience_years(self) -> int:
        adjusted_hire_date = self.hire_date - relativedelta(
            years=self.other_experience_years,
            days=self.other_experience_days,
        )
        return relativedelta(date.today(), adjusted_hire_date).years

    def _get_total_leave_days(self) -> int:
        from leaves.utils import Calendar_utils

        k = Calendar_utils(date.today().year)
        less_10, above_10 = k.max_leave_days()
        return less_10 if self._total_experience_years() < 10 else above_10

    def get_leave_days(self) -> int:
        return self._get_total_leave_days() - self.used_leave_days

    def subtract_leave_days(self, amount: int):
        remaining = self.get_leave_days()
        if amount <= 0 or amount > remaining:
            raise ValueError(
                f"Nieprawidłowa liczba dni: {amount}. Dostępne dni urlopu: {remaining}"
            )
        self.used_leave_days += amount
        self.save()

    def add_leave_days(self, amount: int):
        if amount <= 0:
            raise ValueError("Liczba dni musi być dodatnia.")
        self.used_leave_days = max(0, self.used_leave_days - amount)
        self.save()


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Oczekujący"
        APPROVED = "approved", "Zatwierdzony"
        REJECTED = "rejected", "Odrzucony"
        CANCELED = "canceled", "Anulowany"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_requests",
        verbose_name="Pracownik",
    )

    team = models.ForeignKey(
        "team.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_requests",
        verbose_name="Zespół w momencie wnioskowania",
    )

    start_date = models.DateField(verbose_name="Data od")
    end_date = models.DateField(verbose_name="Data do")
    amount_days = models.PositiveIntegerField(verbose_name="Liczba dni roboczych")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Status",
    )

    request_comment = models.TextField(
        max_length=250,
        blank=True,
        null=True,
        verbose_name="Komentarz wniosku"
    )
    answer_comment = models.TextField(
        max_length=250,
        blank=True,
        null=True,
        verbose_name="Komentarz odpowiedzi"
    )

    who_confirmed = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_leave_requests",
        verbose_name="Potwierdził(a)",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data złożenia")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ostatnia zmiana")


    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Wniosek urlopowy"
        verbose_name_plural = "Wnioski urlopowe"

    def __str__(self):
        return (
            f"{self.employee.first_name} {self.employee.last_name}: "
            f"{self.start_date} – {self.end_date} "
            f"({self.amount_days} dni) [{self.get_status_display()}]"
        )

    def save(self, *args, **kwargs):
        if not self.pk and hasattr(self.employee, "worker_profile") and self.employee.worker_profile.team:
            self.team = self.employee.worker_profile.team

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def team_display_name(self) -> str:
        """Zwraca nazwę zespołu lub informację o jego braku."""
        return self.team.name if self.team else "Brak zespołu"

    def check_is_pending(self):
        if self.status != self.Status.PENDING:
            raise ValueError("Wniosek musi być oczekujący.")

    def approve(self, who):
        self.check_is_pending()
        self.status = self.Status.APPROVED
        self.who_confirmed = who
        self.save()

    def reject(self, who):
        self.check_is_pending()
        self.status = self.Status.REJECTED
        self.who_confirmed = who
        self.save()

    def change_request(self, new_start_date: date, new_end_date: date):
        self.check_is_pending()
        self.start_date = new_start_date
        self.end_date = new_end_date
        self.save()

    def cancel_request(self, who):
        self.check_is_pending()
        self.status = self.Status.CANCELED
        self.who_confirmed = who
        self.save()