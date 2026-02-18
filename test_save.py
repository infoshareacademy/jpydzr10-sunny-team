import os
from database.database import create_user, user_database

print("Przed dodaniem:", len(user_database))

create_user(1, "nowyuser", "abc123hash", "User")
create_user(2, "ola", "test123", "Worker")

print("Po dodaniu:", len(user_database))