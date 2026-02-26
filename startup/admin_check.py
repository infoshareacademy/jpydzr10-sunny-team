from models.admin import Admin
from models.user import User

from database.database import user_database,create_user

if not (any(isinstance(User,Admin) for user in user_database.values())):
    create_user(1,"SuperAdmin","1234","Admin")
else:
    pass