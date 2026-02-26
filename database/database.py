from models.user import User
from models.admin import Admin

user_database = {}

def create_user(user_id: int, username: str ,password_hash: str , role: str):
    if role == "Admin":
        user = Admin(user_id,username,password_hash)
    else:
        user = User(user_id, username, password_hash)
    key = user.user_id

    user_database[key] = user

    return user
