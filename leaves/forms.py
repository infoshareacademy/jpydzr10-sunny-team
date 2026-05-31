from django import forms
from django.core.exceptions import ValidationError
from datetime import date
from .utils import Calendar_utils
from .models import LeaveRequest

class LeaveRequestForm(forms.ModelForm):
    confirmed = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = LeaveRequest
        fields = ['start_date', 'end_date', 'confirmed']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)

    def clean(self):
        cd = super().clean()
        start_date = cd.get('start_date')
        end_date = cd.get('end_date')

        if not start_date or not end_date:
            raise ValidationError("Pola muszą być wypełnione poprawnie zgodnie z formatem dat.")

        from leaves.models import WorkerProfile
        try:
            profile = WorkerProfile.objects.get(user=self.user)
            available_days = profile.get_leave_days()
        except WorkerProfile.DoesNotExist:
            raise ValidationError("Nie znaleziono profilu pracownika.")

        if self.instance and self.instance.pk:
            if start_date == self.instance.start_date and end_date == self.instance.end_date:
                raise ValidationError(
                    "Nie wprowadzono żadnych zmian."
                )

        today = date.today()
        if start_date < today or end_date < today:
            raise ValidationError("Nie można wybrać daty z przeszłości.")
        if start_date > end_date:
            raise ValidationError("Data rozpoczęcia nie może być późniejsza niż zakończenia.")
        if start_date.year != today.year or end_date.year != today.year:
            raise ValidationError(f"Wnioski obsługiwane są jedynie na aktualny rok {today.year}.")

        cal = Calendar_utils(start_date.year)
        count = int(cal.count_leave_days(start_date, end_date))

        if count <= 0:
            raise ValidationError("Wybrany zakres nie obejmuje dni roboczych.")
        if count > available_days:
            raise ValidationError(
                f"Twój wniosek na {count} dni przekracza aktualny limit urlopowy: {available_days} dni."
            )

        overlapping = LeaveRequest.objects.filter(
            employee=self.user,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )

        if self.instance and self.instance.pk:
            overlapping = overlapping.exclude(pk=self.instance.pk)

        if overlapping.exists():
            conflict = overlapping.first()
            raise ValidationError(
                f"Wprowadzone daty obejmują dni z aktywnego wniosku: "
                f"{conflict.start_date.strftime('%d.%m.%Y')} – "
                f"{conflict.end_date.strftime('%d.%m.%Y')}. "
            )

        cd['amount_days'] = count
        return cd

