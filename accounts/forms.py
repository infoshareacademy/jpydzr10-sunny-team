from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

User = get_user_model()

class AddUserForm(UserCreationForm):
    """ Formularz tworzenia uzytkownika przez admina / HR """

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'role',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': "form-control"}) # Pole na hasło
        self.fields['password2'].widget.attrs.update({'class': "form-control"}) # Pole do potwierdzenia hasła


    def save(self, commit=True):
            user = super().save(commit=False)
            if commit:
                user.save()
            return user
