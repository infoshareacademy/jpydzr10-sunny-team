from django.db import models
from django.conf import settings
from datetime import date
from dateutil.relativedelta import relativedelta


class WorkerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # gdy User zostanie usunięty, usuń też profil
        related_name="worker_profile"
    )

    # --- Pola z workers.csv ---
    hire_date = models.DateField()
    other_experience_years = models.IntegerField(default=0)
    other_experience_days = models.IntegerField(default=0)
    used_leave_days = models.IntegerField(default=0)
    team = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Profil pracownika"
        verbose_name_plural = "Profile pracowników"

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.team})"

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

    # def set_leave_days(self, new_value):
    #     if new_value <= 0 or new_value > self._get_total_leave_days()
    #         raise ValueError(f"Podana wartość wykracza poza zakres:{0} - {self._get_total_leave_days()}")
    #         return
    #     self.used_leave_days = self._get_total_leave_days() - new_value
    #
    # def reset_leave_days(self):
    #     self.used_leave_days = 0

    def subtract_leave_days(self, amount: int):
        remaining = self.get_leave_days()
        if amount <= 0 or amount > remaining:
            raise ValueError(
                f"Nieprawidłowa liczba dni: {amount}. "
                f"Dostępne dni urlopu: {remaining}"
            )
        self.used_leave_days += amount
        self.save()

    def add_leave_days(self, amount: int):
        if amount <= 0:
            raise ValueError("Liczba dni musi być dodatnia.")
        self.used_leave_days = max(0, self.used_leave_days - amount)
        self.save()

    # def update_leave_days(self):
    #     ... # leaving empty, since I have no idea where new value would come from