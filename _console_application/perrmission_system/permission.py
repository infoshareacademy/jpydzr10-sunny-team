class Permission:
    """
    System uprawnień aplikacji urlopowej.

    Uprawnienia:
        can_approve_request    - zatwierdzanie wniosków urlopowych
        can_reject_request     - odrzucanie wniosków urlopowych
        can_cancel_request     - anulowanie wniosków (własnych i cudzych)
        can_change_request     - zmiana dat wniosku
        can_see_all_requests   - podgląd wszystkich wniosków w systemie
        can_submit_request     - składanie własnych wniosków urlopowych
        can_see_own_requests   - podgląd własnych wniosków i urlopów
        can_add_user           - dodawanie nowych użytkowników
        can_list_users         - wyświetlanie listy użytkowników
        can_reset_password     - resetowanie hasła użytkownika
        can_see_user_vacations - podgląd urlopów dowolnego użytkownika

    Uwaga dotycząca can_cancel_request:
        Worker może anulować tylko własne wnioski.
        Admin, Manager, HR mogą anulować również cudze wnioski.
        Ta logika jest egzekwowana w startup_app.py, nie tutaj.
    """

    permissions = {
        "Admin": {
            "can_approve_request":    True,
            "can_reject_request":     True,
            "can_cancel_request":     True,
            "can_change_request":     True,
            "can_see_all_requests":   True,
            "can_submit_request":     False,
            "can_see_own_requests":   False,
            "can_add_user":           True,
            "can_list_users":         True,
            "can_reset_password":     True,
            "can_see_user_vacations": True,
        },
        "Manager": {
            "can_approve_request":    True,
            "can_reject_request":     True,
            "can_cancel_request":     True,
            "can_change_request":     False,
            "can_see_all_requests":   True,
            "can_submit_request":     True,
            "can_see_own_requests":   True,
            "can_add_user":           False,
            "can_list_users":         False,
            "can_reset_password":     False,
            "can_see_user_vacations": True,
        },
        "HR": {
            "can_approve_request":    False,
            "can_reject_request":     False,
            "can_cancel_request":     True,
            "can_change_request":     False,
            "can_see_all_requests":   True,
            "can_submit_request":     True,
            "can_see_own_requests":   True,
            "can_add_user":           True,
            "can_list_users":         True,
            "can_reset_password":     False,
            "can_see_user_vacations": True,
        },
        "Worker": {
            "can_approve_request":    False,
            "can_reject_request":     False,
            "can_cancel_request":     True,
            "can_change_request":     True,
            "can_see_all_requests":   False,
            "can_submit_request":     True,
            "can_see_own_requests":   True,
            "can_add_user":           False,
            "can_list_users":         False,
            "can_reset_password":     False,
            "can_see_user_vacations": False,
        },
    }

    @staticmethod
    def verifyPermission(role: str, action: str) -> bool:
        """
        Sprawdza czy dana rola ma uprawnienie do wykonania akcji.
        Zwraca False jeśli rola lub akcja nie istnieje w słowniku.
        """
        try:
            return Permission.permissions[role][action]
        except KeyError:
            print(f"Brak uprawnienia '{action}' dla roli '{role}'")
            return False


if __name__ == "__main__":
    roles = ["Admin", "Manager", "HR", "Worker"]
    actions = [
        "can_approve_request", "can_reject_request", "can_cancel_request",
        "can_change_request", "can_see_all_requests", "can_submit_request",
        "can_see_own_requests", "can_add_user", "can_list_users",
        "can_reset_password", "can_see_user_vacations",
    ]

    col_w = 26
    print(f"\n{'Uprawnienie':<{col_w}} {'Admin':<10} {'Manager':<10} {'HR':<10} {'Worker':<10}")
    print("-" * (col_w + 40))
    for action in actions:
        row = f"{action:<{col_w}}"
        for role in roles:
            val = "✅" if Permission.verifyPermission(role, action) else "❌"
            row += f" {val:<10}"
        print(row)