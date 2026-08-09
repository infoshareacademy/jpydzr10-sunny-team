class User:
    """
    Reprezentuje konto użytkownika w systemie urlopowym.
    Zawiera dane potrzebne do logowania i kontroli dostępu.
    """
    def __init__(self, user_id: int, username: str, password_hash: str, role: str, is_active: bool = True):
        self.user_id = user_id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.is_active = is_active

    def deactivate(self):
        self.is_active = False