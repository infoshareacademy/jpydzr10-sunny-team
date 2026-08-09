from datetime import date
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import LeaveRequest
from .utils import Calendar_utils


class LeaveRequestForm(forms.ModelForm):
    confirmed = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = LeaveRequest
        fields = ['start_date', 'end_date', 'request_comment', 'confirmed']
        labels = {
            'start_date': _('Data rozpoczęcia'),
            'end_date': _('Data zakończenia'),
            'request_comment': _('Komentarz do wniosku'),
        }
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'request_comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Opcjonalny komentarz lub uzasadnienie wniosku...'),
                'maxlength': '250',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)

    def clean(self):
        cd = super().clean()
        start_date = cd.get('start_date')
        end_date = cd.get('end_date')

        if not start_date or not end_date:
            raise ValidationError(_("Pola muszą być wypełnione poprawnie zgodnie z formatem dat."))

        from leaves.models import WorkerProfile
        try:
            profile = WorkerProfile.objects.get(user=self.user)
            available_days = profile.get_leave_days()
        except WorkerProfile.DoesNotExist:
            raise ValidationError(_("Nie znaleziono profilu pracownika."))

        if self.instance and self.instance.pk:
            if start_date == self.instance.start_date and end_date == self.instance.end_date:
                raise ValidationError(_("Nie wprowadzono żadnych zmian."))

        today = date.today()
        if start_date < today or end_date < today:
            raise ValidationError(_("Nie można wybrać daty z przeszłości."))
        if start_date > end_date:
            raise ValidationError(_("Data rozpoczęcia nie może być późniejsza niż zakończenia."))
        if start_date.year != today.year or end_date.year != today.year:
            raise ValidationError(
                _("Wnioski obsługiwane są jedynie na aktualny rok {year}.").format(year=today.year)
            )

        cal = Calendar_utils(start_date.year)
        count = int(cal.count_leave_days(start_date, end_date))

        if count <= 0:
            raise ValidationError(_("Wybrany zakres nie obejmuje dni roboczych."))
        if count > available_days:
            raise ValidationError(
                _("Twój wniosek na {count} dni przekracza aktualny limit urlopowy: {available} dni.").format(
                    count=count, available=available_days
                )
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
                _("Wprowadzone daty obejmują dni z aktywnego wniosku: {start} – {end}.").format(
                    start=conflict.start_date.strftime('%d.%m.%Y'),
                    end=conflict.end_date.strftime('%d.%m.%Y')
                )
            )

        cd['amount_days'] = count
        return cd