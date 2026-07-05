# Role i uprawnienia

System uprawnień jest zdefiniowany w [`accounts/permission.py`](../accounts/permission.py)
w klasie `Permission`. Każdy zalogowany użytkownik ma przypisaną jedną rolę
(pole `role` w modelu `accounts.User`): **Admin**, **Manager**, **HR** lub **Worker**.
Sprawdzanie dostępu do widoków odbywa się przez dekorator `@role_required(...)`
oraz mixin `RoleRequiredMixin`, które porównują aktywną rolę użytkownika z tabelą
uprawnień poniżej.

## Tabela uprawnień

| Uprawnienie              | Opis                                              | Admin | Manager | HR  | Worker |
|---------------------------|---------------------------------------------------|:-----:|:-------:|:---:|:------:|
| `can_submit_request`      | Składanie własnych wniosków urlopowych             |  ❌   |   ✅    | ✅  |  ✅    |
| `can_approve_request`     | Zatwierdzanie wniosków urlopowych                  |  ✅   |   ✅    | ❌  |  ❌    |
| `can_reject_request`      | Odrzucanie wniosków urlopowych                     |  ✅   |   ✅    | ❌  |  ❌    |
| `can_cancel_request`      | Anulowanie wniosków (patrz uwaga niżej)            |  ✅   |   ✅    | ✅  |  ✅    |
| `can_change_request`      | Zmiana dat istniejącego wniosku                    |  ✅   |   ❌    | ❌  |  ✅    |
| `can_see_own_requests`    | Podgląd własnych wniosków i urlopów                |  ❌   |   ✅    | ✅  |  ✅    |
| `can_see_all_requests`    | Podgląd wszystkich wniosków w systemie             |  ✅   |   ✅    | ✅  |  ❌    |
| `can_see_user_vacations`  | Podgląd urlopów dowolnego użytkownika              |  ✅   |   ✅    | ✅  |  ❌    |
| `can_add_user`            | Dodawanie nowych użytkowników                      |  ✅   |   ❌    | ✅  |  ❌    |
| `can_list_users`          | Wyświetlanie listy użytkowników                    |  ✅   |   ❌    | ✅  |  ❌    |
| `can_view_user_list`      | Podgląd listy użytkowników (widok `user_list`)     |  ✅   |   ❌    | ✅  |  ❌    |
| `can_reset_password`      | Resetowanie hasła użytkownika                      |  ✅   |   ❌    | ❌  |  ❌    |
| `can_deactivate_staff`    | Dezaktywacja konta HR/Managera                     |  ✅   |   ❌    | ❌  |  ❌    |
| `can_deactivate_worker`   | Dezaktywacja konta Workera                         |  ✅   |   ✅    | ✅  |  ❌    |

✅ = uprawnienie przyznane, ❌ = brak uprawnienia.

## Uwaga dot. `can_cancel_request`

Wszystkie role formalnie mają `can_cancel_request = True`, ale zakres jest różny:

- **Worker** może anulować **tylko własne** wnioski.
- **Admin, Manager, HR** mogą anulować również wnioski innych użytkowników.

Ta dodatkowa logika (czyje wnioski wolno anulować) jest egzekwowana w warstwie
widoków/logiki biznesowej, a nie w samym słowniku `Permission.permissions`.

## Jak to jest wykorzystywane w kodzie

```python
# w widoku funkcyjnym
@login_required
@role_required("can_add_user")
def add_user(request):
    ...

# w widoku klasowym
class LeaveRequestUpdateView(RoleRequiredMixin, View):
    required_action = "can_change_request"
    ...
```

Aktywna rola brana jest z sesji (`request.session["active_role"]`), a jeśli nie jest
ustawiona — z pola `request.user.role`. Pozwala to np. na (jeśli aplikacja to
wykorzystuje) tymczasowe przełączanie kontekstu roli w ramach sesji.

## Podgląd tabeli z terminala

Plik `accounts/permission.py` da się też uruchomić bezpośrednio — wypisze tabelę
uprawnień w konsoli:

```bash
python accounts/permission.py
```