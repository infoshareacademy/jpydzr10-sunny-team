from models.user import User

class Admin(User):
    def __init__(self, user_id: int, username: str, password_hash: str, role = "Admin"):
        super().__init__(user_id, username, password_hash, role)
