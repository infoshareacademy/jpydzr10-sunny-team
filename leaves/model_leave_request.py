from django.db import models
from django.conf import settings
from datetime import date
from .services import count_leave_days_service


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING  = "pending",  "Oczekujący"
        APPROVED = "approved", "Zatwierdzony"
        REJECTED = "rejected", "Odrzucony"
        CANCELED = "canceled", "Anulowany"


    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_requests",
        verbose_name="Pracownik",
    )

    start_date   = models.DateField(verbose_name="Data od")
    end_date     = models.DateField(verbose_name="Data do")
    amount_days  = models.PositiveIntegerField(verbose_name="Liczba dni roboczych")



    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Status",
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
    updated_at = models.DateTimeField(auto_now=True,     verbose_name="Ostatnia zmiana")



    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Wniosek urlopowy"
        verbose_name_plural = "Wnioski urlopowe"



    def __str__(self):
        return (
            f"{self.first_name} {self.last_name}: "
            f"{self.start_date} – {self.end_date} "
            f"({self.amount_days} dni) [{self.get_status_display()}]"

        )

    def check_is_pending(self):
        if self.status != self.Status.PENDING:
            raise ValueError("Wniosek musi być oczekujący.")

    def clean(self):
        if not self.start_date or not self.end_date:
            return
        try:
            calculated_days = count_leave_days_service(
                self.start_date.strftime('%Y-%m-%d'),
                self.end_date.strftime('%Y-%m-%d')
            )
            self.amount_days = calculated_days

        except ValueError as e:
            raise e

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def approve(self, who: settings.AUTH_USER_MODEL):
        self.check_is_pending()
        self.status = self.Status.APPROVED
        self.who_confirmed = who
        self.save()

    def reject(self, who: settings.AUTH_USER_MODEL):
        self.check_is_pending()
        self.status = self.Status.REJECTED
        self.who_confirmed = who
        self.save()

    def change_request(self, new_start_date: date, new_end_date: date):
        self.check_is_pending()
        self.start_date  = new_start_date
        self.end_date    = new_end_date
        self.save()

    def cancel_request(self, who: settings.AUTH_USER_MODEL):
        self.check_is_pending()
        self.status = self.Status.CANCELED
        self.who_confirmed = who
        self.save()