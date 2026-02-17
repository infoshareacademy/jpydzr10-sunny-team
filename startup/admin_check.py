from models.role import Admin
from models.user_employee import User, Employee
from database.database import user_database,create_user

if not (any(isinstance(user,Admin) for user in user_database.values())):
    create_user(1,"SuperAdmin","1234","Admin")
else:
    pass