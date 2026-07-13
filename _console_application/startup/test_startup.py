from _console_application.auth.login import login
from _console_application.database.database import load_users
from _console_application.leave_requests.leave_request import LeaveRequest
from datetime import date

db = load_users()

# ==========================================
# WORKER - ola / test123
# ==========================================
print("\n=== WORKER (ola) ===")
ola = login("ola", "test123")
print(f"Zalogowano: {ola.username}, rola: {ola.role}")

req = LeaveRequest(ola.user_id, ola.first_name, ola.last_name,
                   date(2025, 8, 1), date(2025, 8, 10), 8)
ola.add_leave_request(req)
print(f"Wnioski urlopowe: {ola.get_leave_requests()}")
ola.remove_leave_request(req)
print(f"Po usunięciu: {ola.get_leave_requests()}")

# ==========================================
# ADMIN - Admin / qwertyuiop
# ==========================================
print("\n=== ADMIN ===")
admin = login("Admin", "qwertyuiop")
print(f"Zalogowano: {admin.username}, rola: {admin.role}")

req2 = LeaveRequest(2, "Ola", "Kowalska",
                    date(2025, 9, 1), date(2025, 9, 5), 5)
req2.approve(admin.username)
print(f"Status po zatwierdzeniu: {req2.status}, przez: {req2.who_confirmed}")

req3 = LeaveRequest(2, "Ola", "Kowalska",
                    date(2025, 10, 1), date(2025, 10, 3), 3)
req3.rejected(admin.username)
print(f"Status po odrzuceniu: {req3.status}")

req4 = LeaveRequest(2, "Ola", "Kowalska",
                    date(2025, 11, 1), date(2025, 11, 5), 5)
req4.cancel_request(admin.username, None)
print(f"Status po anulowaniu: {req4.status}")

req5 = LeaveRequest(2, "Ola", "Kowalska",
                    date(2025, 12, 1), date(2025, 12, 5), 5)
req5.change_request(date(2025, 12, 10), date(2025, 12, 15), 5)
print(f"Po zmianie dat: {req5.start_date} - {req5.end_date}")

# ==========================================
# HR - tomek / 123456789
# ==========================================
print("\n=== HR (tomek) ===")
tomek = login("tomek", "123456789")
print(f"Zalogowano: {tomek.username}, rola: {tomek.role}")
print(f"Imię i nazwisko: {tomek.first_name} {tomek.last_name}")
print(f"Data zatrudnienia: {tomek.hire_date}")
print(f"Doświadczenie: {tomek.total_leave_days}, wykorzystane dni: {tomek.used_leave_days}")

# ==========================================
# MANAGER - janek / jakieshaslo123
# ==========================================
print("\n=== MANAGER (janek) ===")
janek = login("janek", "jakieshaslo123")
print(f"Zalogowano: {janek.username}, rola: {janek.role}")
print(f"Imię i nazwisko: {janek.first_name} {janek.last_name}")
print(f"Data zatrudnienia: {janek.hire_date}")
print(f"Doświadczenie: {janek.total_leave_days}, wykorzystane dni: {janek.used_leave_days}")