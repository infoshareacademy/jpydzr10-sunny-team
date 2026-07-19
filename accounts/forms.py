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
        choices=[],
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

    def __init__(self, *args, allowed_roles=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_roles = allowed_roles or []

        self.fields['password1'].widget.attrs.update({'class': "form-control"})
        self.fields['password2'].widget.attrs.update({'class': "form-control"})

        teams = (
            WorkerProfile.objects
            .values_list('team', flat=True)
            .distinct()
            .order_by('team')
        )
        self.fields['team'].choices = [('', '— brak —')] + [(t, t) for t in teams]

        self.fields['role'].choices = [
            c for c in self.fields['role'].choices if c[0] in self.allowed_roles
        ]

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if role not in self.allowed_roles:
            raise forms.ValidationError('Nie masz uprawnień do nadania tej roli.')
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        return user
