import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class PasswordValidator:
    """
    Walidator sprawdzający, czy hasło zawiera:
    - co najmniej jedną wielką literę
    - co najmniej jedną małą literę
    - co najmniej jedną cyfrę
    - co najmniej jeden znak specjalny
    """

    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("Hasło musi zawierać co najmniej jedną wielką literę."),
                code='password_no_upper',
            )

        if not re.search(r'[a-z]', password):
            raise ValidationError(
                _("Hasło musi zawierać co najmniej jedną małą literę."),
                code='password_no_lower',
            )

        if not re.search(r'\d', password):
            raise ValidationError(
                _("Hasło musi zawierać co najmniej jedną cyfrę."),
                code='password_no_number',
            )

        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-\=\+\[\]\\/]', password):
            raise ValidationError(
                _("Hasło musi zawierać co najmniej jeden znak specjalny."),
                code='password_no_symbol',
            )

    def get_help_text(self):
        return _(
            "Twoje hasło musi zawierać co najmniej jedną wielką literę, "
            "jedną małą literę, jedną cyfrę oraz jeden znak specjalny."
        )