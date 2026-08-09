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


# Hierarchia Ról w Systemie
## Worker < Manager < HR < COO
### Tabela Uprawnień

| Cecha / Uprawnienie | **Worker** | **Manager** | **HR** | **COO** | **Admin** |
| :--- | :--- | :--- | :--- |:---------------------------------------------------------------| :--- |
| **Opis roli** | Zwykły pracownik | Lider / Manager zespołu | Specjalista ds. kadr | Dyrektor Operacyjny (Zarząd) | Konto techniczne / Obsługa systemu |
| **Wgląd w profile** | Tylko swój własny profil | Swój własny + Członków swojego zespołu | Wszyscy *(Worker, Manager, HR, COO)* | Wszyscy w całej firmie | Wszyscy *(widok parametrów konta)* |
| **Składanie wniosków urlopowych** | **TAK** | **TAK** *(po przełączeniu na Worker)* | **TAK** *(po przełączeniu na Worker)* | **TAK** *(po przełączeniu na Worker)*  | **NIE** *(konto techniczne, brak urlopów)* |
| **Komu AKCEPTUJE wnioski?** | **BRAK** | **Workerom** ze swojego zespołu | **Workerom** oraz **Managerom** | **Workerom**, **Managerom**, **HR-om** oraz **Samoakceptacja** | **BRAK** |
 | **Możliwość przypisywania ról** | **BRAK** | **BRAK** | `Worker`, `Manager` | `Worker`, `Manager`, `HR` | **Wszystkie** *(Worker, Manager, HR, COO, Admin)* |
 | **Wgląd w logi systemowe** | **NIE** | **NIE** | **NIE** | **NIE** | **TAK** |
 | **Przełączanie widoków (Context Switching)** | Tylko `Worker` | `Manager` ⇆ `Worker` | `HR` ⇆ `Worker` | `COO` ⇆ `Worker`  | Tylko `Admin` |

---

### Zasady Zespołowe i Przepływy

1. **Widoczność Profilu Workera:**
   * Pracownik z rolą `Worker` ma dostęp wyłącznie do własnego profilu. Nie ma podglądu profili innych pracowników ani członków swojego zespołu.

2. **Kaskada Akceptacji Wniosków:**
   * **Wniosek Workera:** Może akceptować `Manager` (ze swojego zespołu), `HR` oraz `COO`.
   * **Wniosek Managera:** Może akceptować `HR` oraz `COO`.
   * **Wniosek HR:** Może akceptować wyłącznie `COO`.
   * **Wniosek COO:** Jest automatycznie zatwierdzany przez system.

3. **Przełączanie Kontekstu (Context Switching):**
   * Każda rola pracownicza (`Manager`, `HR`, `COO`) sklada własne wnioski urlopowe oraz sprawdza swoje prywatne statystyki **wyłącznie po przełączeniu się na widok `Worker`**.

4. **Izolacja Konta Admina:**
   * `Admin` jest kontem technicznym (bez danych osobowych i urlopów), służącym wyłącznie do obsługi technicznej, zarządzania kontami, resetów haseł i podglądu logów systemowych. Żaden użytkownik biznesowy nie ma możliwości przełączenia się na konto Admina.