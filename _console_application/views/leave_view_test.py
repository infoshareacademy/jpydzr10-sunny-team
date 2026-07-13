from _console_application.views.leave_view import show_team_leave_balance, show_my_leave_balance
from _console_application.database.database import user_database
# pokaz urlop zalogowanego pracownika
user = user_database[13]  # ID przykładowego pracownika
show_my_leave_balance(user)

# pokaz urlop całego zespołu
show_team_leave_balance("A")
show_team_leave_balance("B")

