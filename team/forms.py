from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from .models import Team

User = get_user_model()


def get_user_display_name(user):
    """Zwraca 'Imię Nazwisko (username)' lub sam 'username' jeśli brak imienia i nazwiska."""
    full_name = user.get_full_name()
    if full_name:
        return f"{full_name} ({user.username})"
    return user.username


# Rozszerzone pole wyboru z ładną etykietą "Imię Nazwisko (username)"
class UserMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return get_user_display_name(obj)


class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return get_user_display_name(obj)


# --- 1. FORMULARZ PODSTAWOWYCH DANYCH ZESPOŁU ---
class TeamForm(forms.ModelForm):
    head_manager = UserChoiceField(
        queryset=User.objects.none(),
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Główny Manager",
    )

    co_managers = UserMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
        label="Współzarządzający",
    )

    class Meta:
        model = Team
        fields = ["name", "description", "head_manager", "co_managers"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        managers_qs = User.objects.filter(role="Manager", is_active=True)
        self.fields["head_manager"].queryset = managers_qs
        self.fields["co_managers"].queryset = managers_qs

    def clean(self):
        cleaned_data = super().clean()
        head_manager = cleaned_data.get("head_manager")
        co_managers = cleaned_data.get("co_managers")

        if head_manager and co_managers and head_manager in co_managers:
            raise forms.ValidationError(
                "Główny Manager nie może być jednocześnie Współzarządzającym."
            )
        if not head_manager and co_managers:
            raise forms.ValidationError(
                "Nie można ustawić Współzarządzających bez Głównego Managera."
            )
        return cleaned_data

    def generate_log_details(self, is_create=False) -> str:
        if is_create:
            head = self.cleaned_data.get("head_manager")
            head_str = f" Head: {head.get_full_name() or head.username}." if head else ""
            return f"Utworzono zespół '{self.instance.name}'.{head_str}"[:255]

        changes = []
        if "name" in self.changed_data:
            changes.append(f"Nazwa: '{self.instance.name}'")
        if "head_manager" in self.changed_data:
            new_head = self.cleaned_data.get("head_manager")
            head_name = (new_head.get_full_name() or new_head.username) if new_head else "Brak"
            changes.append(f"Head Manager: {head_name}")
        if "co_managers" in self.changed_data:
            co_mgrs = self.cleaned_data.get("co_managers") or []
            summary = ", ".join(u.get_full_name() or u.username for u in co_mgrs)
            changes.append(f"Co-managers: {summary or 'Brak'}")

        if not changes:
            return f"Zaktualizowano dane zespołu '{self.instance.name}'."
        return f"Edycja zespołu '{self.instance.name}': " + "; ".join(changes)[:230]


# --- 2. FORMULARZ ZARZĄDZANIA CZŁONKAMI ---
class TeamMembersForm(forms.Form):
    members = UserMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
        label="Członkowie zespołu (Workerzy)",
    )

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team

        base_qs = User.objects.filter(role="Worker", is_active=True)
        if self.team and self.team.pk:
            available_users = base_qs.filter(
                Q(worker_profile__team__isnull=True) | Q(worker_profile__team=self.team)
            ).distinct()
            current_members = User.objects.filter(worker_profile__team=self.team)

            self.fields["members"].queryset = available_users
            self.fields["members"].initial = current_members
            self._original_members = set(current_members)
        else:
            self.fields["members"].queryset = base_qs.filter(worker_profile__team__isnull=True)
            self._original_members = set()

    def save(self):
        new_members = set(self.cleaned_data.get("members", []))
        from leaves.models import WorkerProfile

        with transaction.atomic():
            removed_profiles = WorkerProfile.objects.filter(
                team=self.team
            ).exclude(user__in=new_members)

            for profile in removed_profiles:
                profile.team = None
                profile.save()

            added_profiles = WorkerProfile.objects.filter(
                user__in=new_members
            ).exclude(team=self.team)

            for profile in added_profiles:
                profile.team = self.team
                profile.save()

        return new_members

    def generate_log_details(self) -> str:
        new_members = set(self.cleaned_data.get("members") or [])
        added = new_members - self._original_members
        removed = self._original_members - new_members

        changes = []
        if added:
            changes.append("Dodano: " + ", ".join(u.get_full_name() or u.username for u in added))
        if removed:
            changes.append("Usunięto: " + ", ".join(u.get_full_name() or u.username for u in removed))

        if not changes:
            return f"Brak zmian w składzie zespołu '{self.team.name}'."

        return f"Zmiana składu '{self.team.name}': " + "; ".join(changes)[:230]