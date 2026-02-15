import hashlib
from models.user_employee import User

class AuthService:
    def __init__(self, users: list[User]):
        self.users = users

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def login(self, username, password):
        password_hash = self.hash_password(password)

        for user in self.users:
            if user.username == username and user.password_hash == password_hash:
                return True

        return False

