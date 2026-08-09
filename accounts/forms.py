# forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from leaves.models import WorkerProfile
from team.models import Team

User = get_user_model()

TEAM_ASSIGNABLE_ROLES = ['Worker']

ROLE_ASSIGNMENT_PERMISSIONS = {
    'Admin': ['Worker', 'Manager', 'HR', 'COO', 'Admin'],
    'COO': ['Worker', 'Manager', 'HR'],
    'HR': ['Worker', 'Manager'],
}


class AddUserForm(UserCreationForm):
    """
    Tworzy konto użytkownika — tylko dane podstawowe.
    Rola i WorkerProfile nadawane są osobno (WorkerProfileForm).
    """
    first_name = forms.CharField(label='Imię', max_length=150, required=True)
    last_name = forms.CharField(label='Nazwisko', max_length=150, required=True)
    email = forms.EmailField(label='Adres e-mail', required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email')

    field_order = ['first_name', 'last_name', 'username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Hasło'
        self.fields['password2'].label = 'Powtórz hasło'
        self.order_fields(self.field_order)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Użytkownik z tym adresem e-mail już istnieje.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class EditUserForm(forms.ModelForm):
    first_name = forms.CharField(label='Imię', max_length=150, required=True)
    last_name = forms.CharField(label='Nazwisko', max_length=150, required=True)
    email = forms.EmailField(label='Adres e-mail', required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if self.instance and self.instance.pk and self.instance.email:
            if self.instance.email.lower() == email.lower():
                return email
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Użytkownik z tym adresem e-mail już istnieje.')

        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        query = User.objects.filter(username__iexact=username)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)

        if query.exists():
            raise ValidationError('Użytkownik o takim loginie już istnieje.')
        return username

class WorkerProfileForm(forms.Form):
    """Formularz zarządzania rolą i profilem pracownika (WorkerProfile)."""

    role = forms.ChoiceField(label='Rola', choices=[], required=False)
    hire_date = forms.DateField(
        label='Data zatrudnienia',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        input_formats=['%Y-%m-%d'],
        required=True,
    )
    other_experience_years = forms.IntegerField(label='Wcześniejsze doświadczenie (lata)', required=False, min_value=0)
    other_experience_days = forms.IntegerField(label='Wcześniejsze doświadczenie (dni)', required=False, min_value=0)

    def __init__(self, *args, allowed_roles=None, target_user=None, instance=None, user_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_roles = allowed_roles or []
        self.target_user = target_user
        self.instance = instance

        self.can_change_role = (user_role == 'Admin')

        # Wspólna klasa CSS dla wszystkich pól
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

        # Ustawienie dostępnych ról
        self.fields['role'].choices = [('', '— brak —')] + [
            (code, label) for code, label in User.ROLES if code in self.allowed_roles
        ]

        if not self.can_change_role:
            self.fields['role'].disabled = True

        # Wypełnienie danych początkowych (tylko przy GET)
        if not self.is_bound:
            if self.target_user:
                self.fields['role'].initial = self.target_user.role
            if self.instance:
                self.fields['hire_date'].initial = self.instance.hire_date
                self.fields['other_experience_years'].initial = self.instance.other_experience_years
                self.fields['other_experience_days'].initial = self.instance.other_experience_days

    def clean_role(self):
        role = self.cleaned_data.get('role')

        if not self.can_change_role:
            return self.target_user.role if self.target_user else None
        if role and role not in self.allowed_roles:
            raise ValidationError('Nie masz uprawnień do nadania tej roli.')

        return role

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def save(self):
        new_role = self.cleaned_data.get('role') or None
        if self.target_user:
            self.target_user.role = new_role
            self.target_user.save(update_fields=['role'])

        profile = self.instance or WorkerProfile(user=self.target_user)
        if self.instance and hasattr(self.instance, 'team') and self.instance.team:
            profile.team = self.instance.team

        profile.hire_date = self.cleaned_data.get('hire_date')
        profile.other_experience_years = self.cleaned_data.get('other_experience_years') or 0
        profile.other_experience_days = self.cleaned_data.get('other_experience_days') or 0
        profile.save()

        self.instance = profile
        return profile


