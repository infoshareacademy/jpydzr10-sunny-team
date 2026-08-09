from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.template.defaultfilters import truncatechars
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from .models import Team

User = get_user_model()


def get_user_display_name(user) -> str:
    """
    Zwraca czytelną dla użytkownika nazwę reprezentującą obiekt User.
    Format: 'Imię Nazwisko (username)' lub sam 'username' (jeśli imię/nazwisko nie są uzupełnione).
    """
    full_name = user.get_full_name()
    return f"{full_name} ({user.username})" if full_name else user.username


class UserMultipleChoiceField(forms.ModelMultipleChoiceField):
    """
    Pole wielokrotnego wyboru dla obiektów User,
    używające `get_user_display_name` do formatowania etykiet w formularzu.
    """
    def label_from_instance(self, obj):
        """Generuje etykietę opcji dla pojedynczego użytkownika."""
        return get_user_display_name(obj)


class UserChoiceField(forms.ModelChoiceField):
    """
    Pole pojedynczego wyboru dla obiektów User,
    używające `get_user_display_name` do formatowania etykiet w formularzu.
    """
    def label_from_instance(self, obj):
        """Generuje etykietę opcji dla pojedynczego użytkownika."""
        return get_user_display_name(obj)


class TeamForm(forms.ModelForm):
    """
    Formularz służący do tworzenia i edycji podstawowych danych zespołu (nazwa, opis, manager, hr).
    Zabezpiecza rolę HR przed możliwością zmiany opiekuna HR oraz Managera zespołu.
    """
    manager = UserChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Manager zespołu"),
        help_text=_("Manager może zarządzać tylko jednym aktywnym zespołem."),
    )

    hr = UserChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Opiekun HR"),
        help_text=_("Osoba z HR opiekująca się zespołem."),
    )

    class Meta:
        model = Team
        fields = ["name", "description", "manager", "hr"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        """
        Inicjalizuje formularz, dynamicznie filtruje QuerySety dla Managera i HR,
        oraz wyłącza opcję zmiany pól strukturalnych (manager, hr) dla użytkowników z rolą HR.
        """
        super().__init__(*args, **kwargs)
        self.user = user

        # Filtrowanie dostępnych opiekunów HR
        self.fields["hr"].queryset = User.objects.filter(role="HR", is_active=True)

        # Manager nie może być przypisany do innego AKTYWNEGO zespołu
        available_managers = User.objects.filter(role="Manager", is_active=True)
        unassigned_condition = Q(managed_team__isnull=True) | Q(managed_team__is_active=False)

        if self.instance and self.instance.pk:
            available_managers = available_managers.filter(
                unassigned_condition | Q(managed_team=self.instance)
            )
        else:
            available_managers = available_managers.filter(unassigned_condition)

        self.fields["manager"].queryset = available_managers.distinct()

        # Zabezpieczenie: blokada edycji pól Manager i HR dla użytkownika z rolą HR
        if self.user and self.user.role == "HR":
            self.fields["manager"].disabled = True
            self.fields["hr"].disabled = True
            self.fields["manager"].help_text = _("Tylko Administrator może zmienić Managera zespołu.")
            self.fields["hr"].help_text = _("Tylko Administrator może zmienić opiekuna HR zespołu.")

    def clean(self):
        """
        Waliduje poprawność danych zespołu:
        - Weryfikuje, czy wprowadzono jakiekolwiek zmiany.
        - Sprawdza wymóg obecności Managera i HR, gdy zespół posiada już członków.
        - Weryfikuje, czy Manager lub HR nie zostali przypadkowo przypisani jako zwykli pracownicy tego samego zespołu.
        """
        cleaned_data = super().clean()

        if self.instance and self.instance.pk and not self.has_changed():
            raise forms.ValidationError(_("Brak zmian do zapisania."))

        manager = cleaned_data.get("manager")
        hr_usr = cleaned_data.get("hr")
        instance_pk = self.instance.pk if self.instance else None

        # Weryfikacja obecności Managera i HR gdy zespół ma już pracowników
        if instance_pk and getattr(self.instance, "members_count", 0) > 0:
            if not manager:
                self.add_error("manager", _("Zespół posiada członków – przypisanie Managera jest wymagane."))
            if not hr_usr:
                self.add_error("hr", _("Zespół posiada członków – przypisanie HR jest wymagane."))

        # Walidacja: Manager nie może być jednocześnie członkiem tego samego zespołu
        if manager and instance_pk and getattr(manager, "worker_profile", None):
            if manager.worker_profile.team_id == instance_pk:
                manager_name = get_user_display_name(manager)
                self.add_error(
                    "manager",
                    _("Wskazany Manager (%(manager_name)s) należy do tego zespołu jako pracownik. Manager musi należeć do innego zespołu.") % {"manager_name": manager_name},
                )

        # Walidacja: HR nie może być jednocześnie członkiem tego samego zespołu
        if hr_usr and instance_pk and getattr(hr_usr, "worker_profile", None):
            if hr_usr.worker_profile.team_id == instance_pk:
                hr_name = get_user_display_name(hr_usr)
                self.add_error(
                    "hr",
                    _("Wskazana osoba z HR (%(hr_name)s) należy do tego zespołu jako pracownik. Opiekun HR musi należeć do innego zespołu.") % {"hr_name": hr_name},
                )

        return cleaned_data

    def generate_log_details(self, is_create=False) -> str:
        """
        Generuje sformatowany opis zmian wprowadzonych w formularzu,
        przeznaczony do zapisu w historii aktywności (ActivityLog).
        """
        no_value_str = str(_("Brak"))

        if is_create:
            details = []
            if self.cleaned_data.get("name"):
                name_val = self.cleaned_data["name"]
                details.append(str(_("Nazwa: '%(name)s'") % {"name": name_val}))

            mgr = self.cleaned_data.get("manager")
            mgr_val = get_user_display_name(mgr) if mgr else no_value_str
            details.append(str(_("Manager: %(manager)s") % {"manager": mgr_val}))

            hr_usr = self.cleaned_data.get("hr")
            hr_val = get_user_display_name(hr_usr) if hr_usr else no_value_str
            details.append(str(_("HR: %(hr)s") % {"hr": hr_val}))

            desc = self.cleaned_data.get("description")
            if desc:
                desc_val = truncatechars(desc, 60)
                details.append(str(_("Opis: '%(description)s'") % {"description": desc_val}))

            joined_details = "; ".join(details)[:255]
            return str(_("Utworzono zespół: %(details)s") % {"details": joined_details})

        changes = []
        if "name" in self.changed_data:
            name_val = self.cleaned_data.get("name")
            changes.append(str(_("Nazwa: '%(name)s'") % {"name": name_val}))
        if "description" in self.changed_data:
            changes.append(str(_("Opis zespołu")))
        if "manager" in self.changed_data:
            new_mgr = self.cleaned_data.get("manager")
            mgr_val = get_user_display_name(new_mgr) if new_mgr else no_value_str
            changes.append(str(_("Manager: %(manager)s") % {"manager": mgr_val}))
        if "hr" in self.changed_data:
            new_hr = self.cleaned_data.get("hr")
            hr_val = get_user_display_name(new_hr) if new_hr else no_value_str
            changes.append(str(_("HR: %(hr)s") % {"hr": hr_val}))

        joined_changes = "; ".join(changes)[:200]
        return str(_("Zaktualizowano zespół: %(changes)s") % {"changes": joined_changes})


class TeamMembersForm(forms.Form):
    """
    Formularz zarządzania składem osobowym (członkami) zespołu.
    Pozwala przypisywać i odpinać pracowników od danego zespołu.
    """
    members = UserMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
        label=_("Członkowie zespołu"),
        help_text=_("Pracownicy przypisani do tego zespołu (z wyłączeniem Managera i HR)."),
    )

    def __init__(self, *args, team=None, **kwargs):
        """
        Inicjalizuje formularz członków: wyklucza z listy wyboru Managera oraz opiekuna HR
        i przygotowuje listę pracowników przypisanych lub nieprzypisanych do żadnego zespołu.
        """
        super().__init__(*args, **kwargs)
        self.team = team
        base_qs = User.objects.filter(is_active=True, worker_profile__isnull=False)

        if self.team and self.team.pk:
            excluded_ids = {
                uid for uid in (self.team.manager_id, self.team.hr_id) if uid is not None
            }

            available_users = (
                base_qs.filter(
                    Q(worker_profile__team__isnull=True) | Q(worker_profile__team=self.team)
                )
                .exclude(id__in=excluded_ids)
                .distinct()
            )

            current_members = User.objects.filter(worker_profile__team=self.team)

            self.fields["members"].queryset = available_users
            self.fields["members"].initial = current_members
            self._original_members = set(current_members)
        else:
            self.fields["members"].queryset = base_qs.filter(worker_profile__team__isnull=True)
            self._original_members = set()

    def clean(self):
        """
        Waliduje logikę biznesową członków zespołu:
        - Weryfikuje zmianę w składzie.
        - Blokuje dodanie członków, jeśli zespół nie ma jeszcze obsadzonego Managera lub HR.
        - Uniemożliwia wybranie osoby pełniącej rolę Managera lub HR tego zespołu jako zwykłego członka.
        """
        cleaned_data = super().clean()
        new_members = set(cleaned_data.get("members") or [])

        if new_members == self._original_members:
            raise forms.ValidationError(_("Brak zmian w składzie zespołu."))

        if new_members and self.team:
            missing = []
            if not self.team.manager_id:
                missing.append(str(_("Managera")))
            if not self.team.hr_id:
                missing.append(str(_("HR")))

            if missing:
                missing_str = str(_(" oraz ")).join(missing)
                raise forms.ValidationError(
                    _("Nie można dodać pracowników do zespołu, który nie posiada przypisanego %(missing_roles)s.")
                    % {"missing_roles": missing_str}
                )

        if self.team:
            forbidden_users = []
            if self.team.manager_id and self.team.manager in new_members:
                mgr_name = get_user_display_name(self.team.manager)
                forbidden_users.append(str(_("Manager (%(name)s)") % {"name": mgr_name}))
            if self.team.hr_id and self.team.hr in new_members:
                hr_name = get_user_display_name(self.team.hr)
                forbidden_users.append(str(_("HR (%(name)s)") % {"name": hr_name}))

            if forbidden_users:
                users_str = ", ".join(forbidden_users)
                raise forms.ValidationError(
                    _("Wśród wybranych członków znajduje się: %(users)s. Manager oraz HR nie mogą być członkami zespołu, którym zarządzają/opiekują się.")
                    % {"users": users_str}
                )

        return cleaned_data

    def save(self):
        """
        Zapisuje stan w bazie danych wewnątrz atomowej transakcji:
        odpina usuniętych członków oraz przypisuje do zespołu nowo wybranych.
        """
        new_members = set(self.cleaned_data.get("members", []))
        from leaves.models import WorkerProfile

        with transaction.atomic():
            # Odpinamy usuniętych z zespołu członków
            WorkerProfile.objects.filter(team=self.team).exclude(user__in=new_members).update(team=None)
            # Przypisujemy nowych pracowników do zespołu
            WorkerProfile.objects.filter(user__in=new_members).exclude(team=self.team).update(team=self.team)

        return new_members

    def generate_log_details(self) -> str:
        """
        Generuje czytelny podgląd zmian w składzie zespołu.
        Obsługuje zarówno pojedyncze zmiany, jak i masowe dodawanie/usuwanie pracowników.
        """
        new_members = set(self.cleaned_data.get("members") or [])
        added = list(new_members - self._original_members)
        removed = list(self._original_members - new_members)

        changes = []

        def format_people_list(people_list: list, action_type: str) -> str:
            count = len(people_list)
            if count == 0:
                return ""

            if count > 5:
                first_few = ", ".join(get_user_display_name(u) for u in people_list[:3])
                remaining_count = count - 3
                if action_type == "add":
                    return str(
                        _("Dodano %(count)d osób: %(first_few)s oraz %(remaining)d innych")
                        % {"count": count, "first_few": first_few, "remaining": remaining_count}
                    )
                else:
                    return str(
                        _("Usunięto %(count)d osób: %(first_few)s oraz %(remaining)d innych")
                        % {"count": count, "first_few": first_few, "remaining": remaining_count}
                    )

            names = ", ".join(get_user_display_name(u) for u in people_list)
            if action_type == "add":
                return str(_("Dodano: %(names)s") % {"names": names})
            else:
                return str(_("Usunięto: %(names)s") % {"names": names})

        if added:
            changes.append(format_people_list(added, "add"))
        if removed:
            changes.append(format_people_list(removed, "remove"))

        joined_changes = "; ".join(changes)
        log_text = str(_("Zaktualizowano zespół: %(changes)s") % {"changes": joined_changes})
        return truncatechars(log_text, 255)