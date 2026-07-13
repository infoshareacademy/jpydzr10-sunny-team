from _console_application.database.database import create_user, load_users

print("Przed dodaniem:", len(load_users()))

create_user(1, "Admin", "qwertyuiop", "Admin")
create_user(2, "ola", "test123", "Employee")
create_user(3, "tomek", "123456789", "HR")
create_user(4, "janek", "jakieshaslo123", "Manager")

print("Po dodaniu:", len(load_users()))