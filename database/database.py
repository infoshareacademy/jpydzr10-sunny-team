from models.user_employee import User
from models.role import Admin

user_databse = {}

def create_user(user_id: int, username: str ,password_hash: str , role: str):
    if role == "Admin":
        user = Admin(user_id,username,password_hash)
    else:
        user = User(user_id, username, password_hash)
    key = user.user_id

    user_databse[key] = user

    return user
