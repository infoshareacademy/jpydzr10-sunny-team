from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from leaves.models import WorkerProfile

User = get_user_model()

class AddUserForm(UserCreationForm):
    """ Formularz tworzenia uzytkownika przez admina / HR """
    team = forms.ChoiceField(
        label='Zespół',
        choices=[],  # wypełniane dynamicznie w __init__
        required=False,
    )
    hire_date = forms.DateField(
        label='Data zatrudnienia',
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
    )

    other_experience_years = forms.IntegerField(
        label='Staż urlopowy (lata)',
        required=False,
    )

    other_experience_days = forms.IntegerField(
        label='Dopełnienie stażu (dni)',
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': "form-control"}) # Pole na hasło
        self.fields['password2'].widget.attrs.update({'class': "form-control"}) # Pole do potwierdzenia hasła

        teams = (
            WorkerProfile.objects
            .values_list('team', flat=True)
            .distinct()
            .order_by('team')
        )
        choices = [('', '— brak —')] + [(t, t) for t in teams]
        self.fields['team'].choices = choices


    def save(self, commit=True):
            user = super().save(commit=False)
            if commit:
                user.save()
            return user
