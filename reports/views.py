import csv
import io
import json
import os
from dataclasses import dataclass
from datetime import datetime, time
from typing import Iterable, Mapping, Sequence

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q, QuerySet
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone as dj_timezone
from django.utils.functional import Promise

from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from accounts.permission import role_required
from leaves.models import WorkerProfile, LeaveRequest
from logs.models import AuthLog, ActivityLog
from team.models import Team

from django.utils.translation import gettext_lazy as _
from django.utils.text import format_lazy

User = get_user_model()

DATE_FMT = "%Y-%m-%d"
DATETIME_DISPLAY_FMT = "%d.%m.%Y %H:%M"

ROLE_HIERARCHY = {"HR": 2, "Manager": 3, "Worker": 4}


# =========================================================================
# Fonty (Pobrano Roboto, bo klasyczny font nie miał 'ł')
# =========================================================================

FONT_PATH = os.path.join(settings.BASE_DIR, "static", "fonts", "Roboto-Regular.ttf")
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont("Roboto-Regular", FONT_PATH))
    pdfmetrics.registerFont(TTFont("Roboto-Bold", FONT_PATH))
    DEFAULT_FONT = "Roboto-Regular"
    BOLD_FONT = "Roboto-Bold"
else:
    DEFAULT_FONT = "Helvetica"
    BOLD_FONT = "Helvetica-Bold"


class NumberedCanvas(canvas.Canvas):
    """
    Canvas ReportLab, które automatycznie zlicza
    wszystkie strony i dodaje stopkę 'Strona X z Y' do każdej z nich.
    """

    def __init__(self, *args, **kwargs):
        """
        Inicjalizuje obiekt płótna oraz listę do przechowywania stanów poszczególnych stron.
        """
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        """
        Zapisuje bieżący stan strony w pamięci i rozpoczyna nową stronę,
        odkładając jej ostateczne renderowanie do momentu wywołania metody save().
        """
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """
        Renderuje wszystkie zapisane strony z wyliczonym nagłówkiem/stopką
        zawierającą łączną liczbę stron, a następnie zapisuje dokument PDF.
        """
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count: int) -> None:
        """
        Rysuje stopkę z numeracją stron (np. 'Strona 1 z 5') w prawym dolnym rogu strony.
        """
        self.setFont(DEFAULT_FONT, 8)
        self.setFillColor(colors.HexColor("#64748B"))
        page_text = _("Strona %(current)s z %(total)s") % {
            'current': self._pageNumber,
            'total': page_count
        }

        self.drawRightString(A4[0] - 30, 20, str(page_text))


# =========================================================================
# PDF budowa
# =========================================================================

@dataclass(frozen=True)
class PdfStyles:
    """
    Struktura danych przechowująca zbiór spójnych stylów akapitowych (ParagraphStyle)
    używanych do formatowania nagłówków, tekstu i tabel w raportach PDF.
    """
    title: ParagraphStyle
    meta: ParagraphStyle
    cell: ParagraphStyle
    cell_header: ParagraphStyle
    chart_title: ParagraphStyle


def _pdf_styles(*, cell_font_size: float = 9, cell_leading: float = 12) -> PdfStyles:
    """
    Tworzy i zwraca obiekt PdfStyles z zdefiniowanymi stylami akapitowymi.
    Pozwala na dostosowanie rozmiaru czcionki i interlinii w komórkach tabeli.
    """
    base = getSampleStyleSheet()
    return PdfStyles(
        title=ParagraphStyle(
            "ReportTitle", parent=base["Normal"], fontName=BOLD_FONT,
            fontSize=16, leading=20, textColor=colors.HexColor("#1E293B"),
            spaceAfter=8,
        ),
        meta=ParagraphStyle(
            "ReportMeta", parent=base["Normal"], fontName=DEFAULT_FONT,
            fontSize=8.5, leading=12, textColor=colors.HexColor("#475569"),
            spaceAfter=3,
        ),
        cell=ParagraphStyle(
            "TableCell", parent=base["Normal"], fontName=DEFAULT_FONT,
            fontSize=cell_font_size, leading=cell_leading,
            textColor=colors.HexColor("#334155"),
        ),
        cell_header=ParagraphStyle(
            "TableHeaderCell", parent=base["Normal"], fontName=BOLD_FONT,
            fontSize=cell_font_size, leading=cell_leading,
            textColor=colors.HexColor("#0F172A"),
        ),
        chart_title=ParagraphStyle(
            "ChartTitle", parent=base["Normal"], fontName=BOLD_FONT,
            fontSize=10, leading=13, textColor=colors.HexColor("#475569"),
            alignment=1, spaceAfter=10,
        ),
    )


def _pdf_table_style(row_count: int) -> TableStyle:
    """
    Generuje styl tabeli ReportLab z naprzemiennymi kolorami wierszy (naprzemienne tło)
    oraz standardowym obramowaniem.
    """
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        *[
            ("BACKGROUND", (0, i), (-1, i),
             colors.HexColor("#F8FAFC") if i % 2 == 0 else colors.white)
            for i in range(1, row_count)
        ],
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
    ])


def _build_table(headers: Sequence[str], rows: Iterable[Sequence[str]],
                 col_widths: Sequence[float], styles: PdfStyles,) -> Table:
    """
    Buduje i sformatuje obiekt tabeli ReportLab na podstawie przekazanych nagłówków,
    wierszy danych i szerokości kolumn.
    """
    data = [[Paragraph(str(h), styles.cell_header) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(cell), styles.cell) for cell in row])

    table = Table(data, colWidths=list(col_widths), repeatRows=1)
    table.setStyle(_pdf_table_style(len(data)))
    return table


def _add_report_header(elements: list, styles: PdfStyles, *, title: str, request,
    active_role: str | None, filters_desc: str | None = None, record_count: int | None = None, ) -> None:
    """
    Dodaje do listy elementów dokumentu PDF standardowy bloku nagłówka raportu,
    zawierający tytuł, autora, rolę, datę generowania oraz opcjonalne filtry i licznik rekordów.
    """
    author_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
    author_role = active_role or getattr(request.user, "role", None) or "-"
    generation_date = dj_timezone.localtime(dj_timezone.now()).strftime(DATETIME_DISPLAY_FMT)

    elements.append(Paragraph(title, styles.title))

    elements.append(
        Paragraph(
            format_lazy(_("<b>Wygenerowano przez:</b> {name}"), name=author_name),
            styles.meta,
        )
    )
    elements.append(
        Paragraph(
            format_lazy(_("<b>Rola użytkownika:</b> {role}"), role=author_role),
            styles.meta,
        )
    )
    elements.append(
        Paragraph(
            format_lazy(_("<b>Data utworzenia:</b> {date}"), date=generation_date),
            styles.meta,
        )
    )

    if filters_desc is not None:
        elements.append(
            Paragraph(
                format_lazy(_("<b>Zastosowane filtry:</b> {filters}"), filters=filters_desc),
                styles.meta,
            )
        )

    if record_count is not None:
        elements.append(
            Paragraph(
                format_lazy(_("<b>Liczba rekordów:</b> {count}"), count=record_count),
                styles.meta,
            )
        )

    elements.append(Spacer(1, 15))


def _new_pdf_document() -> tuple[io.BytesIO, SimpleDocTemplate]:
    """
    Tworzy nowy bufor pamięci BytesIO oraz szablon dokumentu PDF (SimpleDocTemplate)
    z domyślnymi marginesami i rozmiarem A4.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=portrait(A4),
        rightMargin=30, leftMargin=30, topMargin=35, bottomMargin=35,
    )
    return buffer, doc


def _pdf_response(buffer: io.BytesIO, doc: SimpleDocTemplate, elements: list, filename_prefix: str):
    """
    Generuje dokument PDF z przekazanych elementów i zwraca go jako obiekt HttpResponse
    przygotowany do pobrania pliku.
    """
    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)

    filename_date = datetime.now().strftime(DATE_FMT)
    clean_prefix = str(filename_prefix)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{clean_prefix}_{filename_date}.pdf"'
    return response


def _csv_response(filename_prefix: str, header_row: Sequence, rows: Iterable[Sequence], delimiter: str = ";"):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    filename_date = datetime.now().strftime(DATE_FMT)
    clean_prefix = str(filename_prefix)
    response["Content-Disposition"] = f'attachment; filename="{clean_prefix}_{filename_date}.csv"'

    writer = csv.writer(response, delimiter=delimiter)
    writer.writerow([str(h) for h in header_row])

    for row in rows:
        writer.writerow([str(cell) if isinstance(cell, Promise) else cell for cell in row])

    return response


# =========================================================================
# Helper do filtrów
# =========================================================================

def _get_active_role(request) -> str | None:
    """
    Pobiera i zwraca aktualną aktywną rolę użytkownika z sesji lub bezpośrednio z obiektu użytkownika.
    """
    return request.session.get("active_role", getattr(request.user, "role", None))


def _manager_is_restricted(request) -> bool:
    """
    Sprawdza, czy aktywną rolą użytkownika jest 'Manager' i czy ma ograniczony dostęp do danego raportu.
    """
    return _get_active_role(request) == "Manager"


def _get_applied_filters_text(filters_dict: Mapping[str, str | None]) -> str:
    """
    Formatuje słownik aktywnych filtrów do postaci czytelnego ciągu tekstowego opisanego w raporcie.
    """
    active_filters = [f"{str(label)}: {val}" for label, val in filters_dict.items() if val]
    return ", ".join(active_filters) if active_filters else _("Brak (wszystkie rekordy)")


def _get_user_display_name(user_id_str: str) -> str:
    """
    Pobiera nazwę użytkownika (username) na podstawie jego ID podanego jako ciąg znaków.
    """
    if not user_id_str:
        return ""
    try:
        return User.objects.get(id=int(user_id_str)).username
    except (ValueError, User.DoesNotExist):
        return user_id_str


def _apply_date_range(qs: QuerySet, date_from: str, date_to: str, field_name: str) -> QuerySet:
    """
    Filtruje zapytanie QuerySet według zakresu dat dla wskazanego pola, uwzględniając pełne granice dni.
    """
    if date_from:
        try:
            start_date = datetime.strptime(date_from, DATE_FMT).date()
            start = dj_timezone.make_aware(datetime.combine(start_date, time.min))
            qs = qs.filter(**{f"{field_name}__gte": start})
        except ValueError:
            pass

    if date_to:
        try:
            end_date = datetime.strptime(date_to, DATE_FMT).date()
            end = dj_timezone.make_aware(datetime.combine(end_date, time.max))
            qs = qs.filter(**{f"{field_name}__lte": end})
        except ValueError:
            pass

    return qs


@login_required
@role_required("can_export_requests")
def reports_index(request):
    """
    Renderuje stronę główną indeksu raportów.
    """
    return render(request, "reports/index.html")


# =========================================================================
# Raport: użytkownicy per rola
# =========================================================================

def _get_users_per_role_data() -> list[dict]:
    """
    Pobiera dane statystyczne dotyczące liczby użytkowników oraz aktywnych użytkowników
    przypisanych do poszczególnych ról w systemie.
    """
    target_roles = [
        (None, _("Brak roli")),
        ("Worker", "Worker"),
        ("Manager", "Manager"),
        ("HR", "HR"),
    ]

    allowed_role_keys = [key for key, _ in target_roles if key is not None]
    base_filter = Q(role__in=allowed_role_keys) | Q(role__isnull=True) | Q(role="")

    role_stats = (
        User.objects
        .filter(base_filter)
        .values("role")
        .annotate(total=Count("id"), active=Count("id", filter=Q(is_active=True)))
    )

    stats_map = {
        row["role"] or None: {"total": row["total"], "active": row["active"]}
        for row in role_stats
    }

    report_rows = []
    for role_key, role_display in target_roles:
        if role_key is None:
            data = stats_map.get(None, {"total": 0, "active": 0})
            empty_str_data = stats_map.get("", {"total": 0, "active": 0})
            total = data["total"] + empty_str_data["total"]
            active = data["active"] + empty_str_data["active"]
        else:
            data = stats_map.get(role_key, {"total": 0, "active": 0})
            total = data["total"]
            active = data["active"]

        percent_active = round(active / total * 100, 1) if total else 0.0

        report_rows.append({
            "role": role_display,
            "total": total,
            "active": active,
            "percent_active": percent_active,
        })

    return report_rows


@login_required
@role_required("can_view_logs")
def users_per_role_report(request):
    """
    Widok raportu podsumowującego użytkowników według ról z danymi do wykresów.
    """
    if _manager_is_restricted(request):
        return redirect("home")

    report_rows = _get_users_per_role_data()
    context = {
        "report_rows": report_rows,
        "chart_labels": json.dumps([row["role"] for row in report_rows], cls=DjangoJSONEncoder),
        "chart_data_total": json.dumps([row["total"] for row in report_rows]),
        "chart_data_active": json.dumps([row["active"] for row in report_rows]),
    }
    return render(request, "reports/users_per_role.html", context)


@login_required
@role_required("can_view_logs")
def export_users_per_role_csv(request):
    """
    Eksportuje dane z raportu użytkowników według ról do pliku CSV.
    """
    if _manager_is_restricted(request):
        return redirect("home")

    report_rows = _get_users_per_role_data()
    rows = [
        [row["role"], row["total"], row["active"], f"{row['percent_active']}%"]
        for row in report_rows
    ]
    return _csv_response(
        _("raport_role"),
        [
            _("Rola"),
            _("Liczba użytkowników"),
            _("Aktywni"),
            _("% aktywnych"),
        ],
        rows,
    )


@login_required
@role_required("can_view_logs")
def export_users_per_role_pdf(request):
    """
    Generuje i zwraca raport w postaci pliku PDF przedstawiający podział
    użytkowników na role wraz z wykresem kołowym.
    """
    if _manager_is_restricted(request):
        return redirect("home")

    active_role = _get_active_role(request)
    include_inactive = request.GET.get("include_inactive", "true").lower() == "true"
    report_rows = _get_users_per_role_data()

    styles = _pdf_styles()
    buffer, doc = _new_pdf_document()
    elements = []

    _add_report_header(
        elements, styles,
        title=_("Raport Użytkowników: Role"),
        request=request, active_role=active_role,
    )

    table_rows = [
        [row["role"], row["total"], row["active"], f"{row['percent_active']}%"]
        for row in report_rows
    ]
    headers = [
        _("Rola"),
        _("Liczba użytkowników"),
        _("Aktywni"),
        _("% aktywnych"),
    ]

    elements.append(_build_table(
        headers,
        table_rows,
        [160, 125, 125, 125],
        styles,
    ))
    elements.append(Spacer(1, 20))
    chart_info_text = (
        _("* Wykres uwzględnia: Wszyscy użytkownicy (aktywni i nieaktywni)")
        if include_inactive else
        _("* Wykres uwzględnia: Tylko aktywni użytkownicy")
    )
    elements.append(Paragraph(str(chart_info_text), styles.chart_title))
    elements.append(Spacer(1, 10))
    elements.append(_build_users_per_role_pie(report_rows, include_inactive))

    return _pdf_response(buffer, doc, elements, _("raport_role"))

def _build_users_per_role_pie(report_rows: list[dict], include_inactive: bool) -> Drawing:
    """
    Tworzy i konfiguruje obiekt wykresu kołowego ReportLab (Drawing) na potrzeby raportu PDF.
    """
    pie_data = [row["total"] if include_inactive else row["active"] for row in report_rows]
    pie_labels = [f"{str(row['role'])} ({val})" for row, val in zip(report_rows, pie_data)]

    drawing = Drawing(535, 180)
    pie = Pie()
    pie.x, pie.y = 180, 0
    pie.width = pie.height = 150
    pie.data = pie_data if sum(pie_data) > 0 else [1]
    pie.labels = pie_labels
    pie.innerRadiusFraction = 0.55

    chart_colors = [
        colors.HexColor("#94A3B8"),
        colors.HexColor("#3B82F6"),
        colors.HexColor("#1D4ED8"),
        colors.HexColor("#1E40AF"),
        colors.HexColor("#1E3A8A"),
    ]
    for i in range(len(pie_data)):
        pie.slices[i].fillColor = chart_colors[i % len(chart_colors)]
        pie.slices[i].strokeColor = colors.white
        pie.slices[i].strokeWidth = 1.5
        pie.slices[i].fontName = DEFAULT_FONT
        pie.slices[i].fontSize = 8.5

    drawing.add(pie)
    return drawing


# =========================================================================
# Raport: wykorzystanie urlopów per pracownik
# =========================================================================

def _leave_usage_profiles(request, active_role: str | None):
    """
    Zwraca skorygowany zestaw profili pracowników (WorkerProfile)
    uwzględniający uprawnienia i aktywną rolę użytkownika.
    """
    profiles = WorkerProfile.objects.select_related("user", "team").filter(user__is_active=True)

    if active_role in ("Manager", "HR"):
        managed_teams = Team.objects.for_user(request.user).filter(is_active=True)
        profiles = profiles.filter(team__in=managed_teams).distinct()
    else:
        active_teams = Team.objects.filter(is_active=True)
        profiles = profiles.filter(Q(team__in=active_teams) | Q(team__isnull=True)).distinct()

    return profiles


def _get_teams_info_for_profile(profile) -> list[dict]:
    """
    Zwraca zespół, do którego należy profil
    """
    if profile.team and profile.team.is_active:
        return [{"id": profile.team.id, "name": profile.team.name}]
    return []


def _leave_usage_rows(profiles, role_filter: str | None = None, team_filter: str | None = None) -> list[dict]:
    """
    Przetwarza listę profili pracowników i wylicza dane dotyczące wykorzystania ich urlopów uwzględniając podane filtry.
    """
    rows = []
    for profile in profiles:
        role_display = getattr(profile.user, "role", None) or "-"
        teams_list = _get_teams_info_for_profile(profile)

        if role_filter and role_filter != "ALL" and role_display != role_filter:
            continue

        if team_filter and team_filter != "ALL":
            if team_filter == "NONE":
                if teams_list:
                    continue
            else:
                team_ids = [str(t["id"]) for t in teams_list]
                if team_filter not in team_ids:
                    continue

        total = profile._get_total_leave_days()
        used = profile.used_leave_days
        remaining = profile.get_leave_days()
        percent_used = round(used / total * 100, 1) if total else 0.0

        rows.append({
            "profile_id": profile.id,
            "user_id": profile.user.id,
            "first_name": profile.user.first_name,
            "last_name": profile.user.last_name,
            "role": role_display,
            "role_priority": ROLE_HIERARCHY.get(role_display, 99),
            "teams": teams_list,
            "total": total,
            "used": used,
            "remaining": remaining,
            "percent_used": percent_used,
        })

    rows.sort(key=lambda x: (x["role_priority"], x["last_name"].lower(), x["first_name"].lower()))
    return rows


@login_required
@role_required("can_export_requests")
def leave_usage_report(request):
    active_role = _get_active_role(request)
    team_filter = request.GET.get("team", "ALL")

    if active_role in ("Manager", "HR"):
        if team_filter == "NONE":
            team_filter = "ALL"

    profiles = _leave_usage_profiles(request, active_role)
    report_rows = _leave_usage_rows(profiles, team_filter=team_filter)

    if active_role in ("Manager", "HR"):
        all_teams = Team.objects.for_user(request.user).filter(is_active=True).order_by("name")
        show_no_team_option = False
    else:
        all_teams = Team.objects.filter(is_active=True).order_by("name")
        show_no_team_option = True

    context = {
        "report_rows": report_rows,
        "all_roles": ["HR", "Manager", "Worker"],
        "all_teams": all_teams,
        "selected_team": team_filter,
        "show_no_team_option": show_no_team_option,
    }
    return render(request, "reports/leave_usage.html", context)


@login_required
@role_required("can_export_requests")
def export_leave_usage_csv(request):
    """
    Generuje plik CSV zawierający podsumowanie wykorzystania urlopów dla poszczególnych pracowników.
    """
    active_role = _get_active_role(request)
    team_filter = request.GET.get("team", "ALL")

    profiles = _leave_usage_profiles(request, active_role)
    report_rows = _leave_usage_rows(profiles, team_filter)

    rows = []
    for row in report_rows:
        teams_str = ", ".join(t["name"] for t in row["teams"]) if row["teams"] else "-"
        rows.append([
            row["first_name"], row["last_name"], teams_str,
            row["total"], row["used"], row["remaining"], f"{row['percent_used']}%",
        ])

    return _csv_response(
        _("raport_pracownicy"),
        [
            _("Imię"),
            _("Nazwisko"),
            _("Zespół"),
            _("Przydzielone dni"),
            _("Wykorzystane dni"),
            _("Pozostałe dni"),
            _("% wykorzystania"),
        ],
        rows,
    )


@login_required
@role_required("can_export_requests")
def export_leave_usage_pdf(request):
    """
    Tworzy plik PDF przedstawiający indywidualny raport wykorzystania urlopów przez pracowników.
    """
    active_role = _get_active_role(request)
    team_filter = request.GET.get("team", "ALL")

    profiles = _leave_usage_profiles(request, active_role)
    report_rows = _leave_usage_rows(profiles, team_filter)

    if team_filter == "ALL":
        team_display_name = _("Wszystkie")
    elif team_filter == "NONE":
        team_display_name = _("Brak zespołu")
    else:
        team_obj = Team.objects.filter(id=team_filter).first()
        team_display_name = team_obj.name if team_obj else team_filter
    filters_desc = None
    if active_role in ("Manager", "HR"):
        filters_desc = format_lazy("{label}: <i>{team}</i>", label=_("Zespół"), team=team_display_name)

    styles = _pdf_styles(cell_font_size=8.5, cell_leading=11)
    buffer, doc = _new_pdf_document()
    elements = []

    _add_report_header(
        elements, styles,
        title=_("Raport Wykorzystania Urlopów: Pracownicy"),
    request=request, active_role=active_role, filters_desc=filters_desc,
    )

    table_rows = []
    for row in report_rows:
        full_name = f"{row['first_name']} {row['last_name']}"
        teams_pdf_html = "<br/>".join(t["name"] for t in row["teams"]) if row["teams"] else "-"
        table_rows.append([
            full_name,  teams_pdf_html,
            row["total"], row["used"], row["remaining"], f"{row['percent_used']}%",
        ])

    elements.append(_build_table(
        [_("Pracownik"), _("Zespół"), _("Przydzielone"), _("Wykorzystane"), _("Pozostałe"), _("% wykorzystania")],
    table_rows,
        [100, 95, 75, 85, 75, 95],
        styles,
    ))

    return _pdf_response(buffer, doc, elements, _("raport_pracownicy"))


# =========================================================================
# Raport: wykorzystanie urlopów per zespół
# =========================================================================

def _default_team_agg(team_id, team_name: str) -> dict:
    """
    Tworzy słownik ze zczytanymi domyślnie pustymi wartościami agregacyjnymi dla pojedynczego zespołu.
    """
    return {"team_id": team_id, "team": team_name, "members": 0, "total": 0, "used": 0, "remaining": 0}


def _team_rows(request) -> list[dict]:
    """
    Agreguje i przelicza dane urlopowe pracowników w rozbiciu na poszczególne zespoły.
    Do agregacji wliczani są wszyscy członkowie zespołu niezależnie od roli,
    z wyjątkiem osoby pełniącej funkcję Managera lub HR danego zespołu.
    """
    active_role = _get_active_role(request)
    profiles = _leave_usage_profiles(request, active_role)
    active_profiles = [p for p in profiles if getattr(p.user, "is_active", True)]
    user_rows = _leave_usage_rows(active_profiles)

    if active_role in ("Manager", "HR"):
        managed_teams_qs = Team.objects.for_user(request.user).filter(is_active=True)
        allowed_team_ids = set(managed_teams_qs.values_list("pk", flat=True))
    else:
        managed_teams_qs = Team.objects.filter(is_active=True)
        allowed_team_ids = None

    # Mapa pk -> obiekt zespołu (potrzebne manager_id/hr_id do wykluczeń)
    team_objs = {t.pk: t for t in managed_teams_qs}
    teams = {pk: _default_team_agg(pk, t.name) for pk, t in team_objs.items()}

    for row in user_rows:
        teams_list = row["teams"]
        user_id = row["user_id"]

        if not teams_list:
            if active_role in ("Manager", "HR"):
                continue
            targets = [("no_team", None, _("Brak zespołu"))]  # Poprawka: _()
        else:
            targets = [(t["id"], t["id"], t["name"]) for t in teams_list]

        for team_key, team_id, team_name in targets:
            if allowed_team_ids is not None and team_key != "no_team" and team_id not in allowed_team_ids:
                continue

            # Wykluczamy Managera/HR TEGO KONKRETNEGO zespołu z agregacji
            if team_key != "no_team":
                team_obj = team_objs.get(team_id)
                if team_obj and (team_obj.manager_id == user_id or team_obj.hr_id == user_id):
                    continue

            agg = teams.setdefault(team_key, _default_team_agg(team_id, team_name))
            agg["members"] += 1
            agg["total"] += row["total"]
            agg["used"] += row["used"]
            agg["remaining"] += row["remaining"]

    report_rows = list(teams.values())
    for agg in report_rows:
        agg["percent_used"] = round(agg["used"] / agg["total"] * 100, 1) if agg["total"] else 0

    report_rows.sort(key=lambda x: str(x["team"]))
    return report_rows


@login_required
@role_required("can_export_requests")
def team_report(request):
    """
    Widok raportu zawierający zbiorcze statystyki wykorzystania urlopów z podziałem na zespoły.
    """
    return render(request, "reports/team_report.html", {"report_rows": _team_rows(request)})


@login_required
@role_required("can_export_requests")
def export_team_report_csv(request):
    """
    Generuje plik CSV zawierający podsumowanie zbiorczych statystyk urlopowych z rozbiciem na zespoły.
    """
    report_rows = _team_rows(request)
    rows = [
        [row["team"], row["members"], row["total"], row["used"], row["remaining"], row["percent_used"]]
        for row in report_rows
    ]
    return _csv_response(
        _("raport_zespoly"),  # Poprawka: _()
        [
            _("Zespół"),
            _("Liczba osób"),
            _("Przydzielone dni (suma)"),
            _("Wykorzystane dni (suma)"),
            _("Pozostałe dni (suma)"),
            _("% wykorzystania"),
        ],  # Poprawka: _()
        rows,
        delimiter=",",
    )


@login_required
@role_required("can_export_requests")
def export_team_report_pdf(request):
    """
    Tworzy plik PDF przedstawiający zestawienie statystyk wykorzystania urlopów zagregowanych według zespołów.
    """
    active_role = _get_active_role(request)
    report_rows = _team_rows(request)

    styles = _pdf_styles(cell_font_size=8.5, cell_leading=11)
    buffer, doc = _new_pdf_document()
    elements = []

    _add_report_header(
        elements, styles,
        title=_("Raport Wykorzystania Urlopów: Zespoły"),  # Poprawka: _()
        request=request, active_role=active_role,
    )

    days_suffix = _("dni")
    table_rows = [
        [
            row["team"],
            row["members"],
            f"{row['total']} {days_suffix}",
            f"{row['used']} {days_suffix}",
            f"{row['remaining']} {days_suffix}",
            f"{row['percent_used']}%",
        ]
        for row in report_rows
    ]
    elements.append(_build_table(
        [
            _("Zespół"),
            _("Liczba osób"),
            _("Przydzielone (suma)"),
            _("Wykorzystane (suma)"),
            _("Pozostałe (suma)"),
            _("% wykorzystania"),
        ],  # Poprawka: _()
        table_rows,
        [110, 75, 90, 90, 75, 85],
        styles,
    ))

    return _pdf_response(buffer, doc, elements, _("raport_zespoly"))  # Poprawka: _()


# =========================================================================
# Eksporty: Activity log
# =========================================================================

def _activity_log_filters(request) -> dict:
    """
    Pobiera filtry logów aktywności z parametrów zapytania HTTP (GET).
    """
    return {
        "action": request.GET.get("action", ""),
        "object_type": request.GET.get("object_type", ""),
        "user": request.GET.get("user", ""),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
    }


def _filtered_activity_logs(filters: dict) -> QuerySet:
    """
    Zwraca zapytanie QuerySet z filtrowanymi wpisami z logu aktywności (ActivityLog).
    """
    logs = ActivityLog.objects.select_related("who").order_by("-created_at")

    if filters["action"]:
        logs = logs.filter(action=filters["action"])
    if filters["object_type"]:
        logs = logs.filter(object_type=filters["object_type"])
    if filters["user"]:
        try:
            logs = logs.filter(who_id=int(filters["user"]))
        except ValueError:
            pass

    return _apply_date_range(logs, filters["date_from"], filters["date_to"], "created_at")


@login_required
@role_required("can_view_logs")
def export_activity_log_csv(request):
    """
    Eksportuje wyfiltrowane logi aktywności do pliku CSV.
    """
    filters = _activity_log_filters(request)
    logs = _filtered_activity_logs(filters)

    rows = []
    for log in logs:
        local_time = dj_timezone.localtime(log.created_at).strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "-"
        rows.append([
            local_time,
            str(log.who) if log.who else "-",
            log.get_action_display(),
            log.get_object_type_display(),
            log.object_id if log.object_id is not None else "-",
            log.details or "-",
        ])

    return _csv_response(
        _("raport_log_aktywnosc"),
        [
            _("Data i czas"),
            _("Użytkownik"),
            _("Akcja"),
            _("Typ obiektu"),
            _("ID obiektu"),
            _("Szczegóły"),
        ],
        rows,
    )


@login_required
@role_required("can_view_logs")
def export_activity_log_pdf(request):
    """
    Generuje plik PDF zawierający przefiltrowany raport logów aktywności systemowej.
    """
    filters = _activity_log_filters(request)
    logs = _filtered_activity_logs(filters)
    active_role = _get_active_role(request)

    filters_desc = _get_applied_filters_text({
        _("Akcja"): filters["action"],
        _("Typ obiektu"): filters["object_type"],
        _("Użytkownik"): _get_user_display_name(filters["user"]),
        _("Data od"): filters["date_from"],
        _("Data do"): filters["date_to"],
    })

    styles = _pdf_styles(cell_font_size=8, cell_leading=10)
    buffer, doc = _new_pdf_document()
    elements = []

    _add_report_header(
        elements, styles,
        title=_("Raport Logów Aktywności"),
        request=request, active_role=active_role,
        filters_desc=filters_desc, record_count=logs.count(),
    )

    table_rows = []
    for log in logs:
        local_time = dj_timezone.localtime(log.created_at).strftime("%Y-%m-%d %H:%M") if log.created_at else "-"
        table_rows.append([
            local_time,
            str(log.who) if log.who else "-",
            log.get_action_display(),
            log.get_object_type_display(),
            log.object_id if log.object_id is not None else "-",
            log.details or "-",
        ])

    elements.append(_build_table(
        [
            _("Data i czas"),
            _("Użytkownik"),
            _("Akcja"),
            _("Typ obiektu"),
            _("ID obiektu"),
            _("Szczegóły"),
        ],
        table_rows,
        [75, 80, 70, 85, 55, 170],
        styles,
    ))

    return _pdf_response(buffer, doc, elements, _("raport_log_aktywnosc"))


# =========================================================================
# Eksporty: Auth log
# =========================================================================

def _auth_log_filters(request) -> dict:
    """
    Pobiera parametry filtrowania logów zdarzeń uwierzytelniania z adresu URL.
    """
    return {
        "action": request.GET.get("action", ""),
        "severity": request.GET.get("severity", ""),
        "user": request.GET.get("user", ""),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
    }


def _filtered_auth_logs(filters: dict) -> QuerySet:
    """
    Zwraca QuerySet z wyfiltrowanymi wpisami logów uwierzytelniania (AuthLog).
    """
    logs = AuthLog.objects.select_related("user").order_by("-timestamp")

    if filters["action"]:
        logs = logs.filter(action=filters["action"])
    if filters["severity"]:
        logs = logs.filter(severity=filters["severity"])
    if filters["user"]:
        try:
            logs = logs.filter(user_id=int(filters["user"]))
        except ValueError:
            pass

    return _apply_date_range(logs, filters["date_from"], filters["date_to"], "timestamp")


@login_required
@role_required("can_view_logs")
def export_auth_log_csv(request):
    """
    Eksportuje przefiltrowane logi uwierzytelniania do pliku w formacie CSV.
    """
    filters = _auth_log_filters(request)
    logs = _filtered_auth_logs(filters)

    rows = []
    for log in logs:
        local_time = dj_timezone.localtime(log.timestamp).strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "-"
        rows.append([
            local_time,
            log.user.get_username() if log.user else _("Anonim"),
            log.get_action_display(),
            log.get_severity_display(),
            log.ip_address or "-",
            log.details or "-",
        ])

    return _csv_response(
        _("raport_log_autoryzacja"),
        [
            _("Data i czas"),
            _("Użytkownik"),
            _("Akcja"),
            _("Poziom"),
            _("Adres IP"),
            _("Szczegóły"),
        ],
        rows,
    )


@login_required
@role_required("can_view_logs")
def export_auth_log_pdf(request):
    """
    Generuje raport w formacie PDF zawierający przefiltrowaną listę logów uwierzytelniania.
    """
    filters = _auth_log_filters(request)
    logs = _filtered_auth_logs(filters)
    active_role = _get_active_role(request)

    filters_desc = _get_applied_filters_text({
        _("Akcja"): filters["action"],
        _("Poziom (severity)"): filters["severity"],
        _("Użytkownik"): _get_user_display_name(filters["user"]),
        _("Data od"): filters["date_from"],
        _("Data do"): filters["date_to"],
    })

    styles = _pdf_styles(cell_font_size=8, cell_leading=10)
    buffer, doc = _new_pdf_document()
    elements = []

    _add_report_header(
        elements, styles,
        title=_("Raport Logów Uwierzytelniania"),
        request=request, active_role=active_role,
        filters_desc=filters_desc, record_count=logs.count(),
    )

    table_rows = []
    for log in logs:
        local_time = dj_timezone.localtime(log.timestamp).strftime("%Y-%m-%d %H:%M") if log.timestamp else "-"
        table_rows.append([
            local_time,
            log.user.get_username() if log.user else _("Anonim"),
            log.get_action_display(),
            log.get_severity_display(),
            log.ip_address or "-",
            log.details or "-",
        ])

    elements.append(_build_table(
        [
            _("Data i czas"),
            _("Użytkownik"),
            _("Akcja"),
            _("Poziom"),
            _("Adres IP"),
            _("Szczegóły"),
        ],
        table_rows,
        [80, 75, 100, 60, 80, 140],
        styles,
    ))

    return _pdf_response(buffer, doc, elements, _("raport_log_autoryzacja"))


# =========================================================================
# Widoczność i filtracja wniosków urlopowych
# =========================================================================

def _get_managed_team_ids(user) -> list:
    """
    Zwraca listę identyfikatorów (PK) zespołów, którymi zarządza podany użytkownik
    (Manager lub HR). Admin obsługiwany osobno w miejscach wywołania.
    """
    return list(Team.objects.for_user(user).values_list("pk", flat=True))


def _base_visible_queryset(request, active_role: str | None) -> QuerySet:
    """
    Konstruuje bazowy QuerySet wniosków urlopowych, do których zalogowany użytkownik
    ma dostęp wynikający z jego aktywnej roli:
    - Worker: tylko własne wnioski
    - Manager / HR: wnioski osób z zespołów, którymi zarządzają (rola pracownika bez znaczenia)
    - Admin: wszystkie wnioski (poza wnioskami innych Adminów)
    """
    qs = LeaveRequest.objects.select_related(
        "employee", "who_confirmed",
        "employee__worker_profile", "employee__worker_profile__team",
    )

    if active_role == "Worker":
        return qs.filter(employee=request.user)

    if active_role in ("Manager", "HR"):
        managed_team_ids = _get_managed_team_ids(request.user)
        if not managed_team_ids:
            return qs.none()
        return qs.filter(employee__worker_profile__team_id__in=managed_team_ids)

    if active_role != "Admin":
        return qs.none()

    return qs.exclude(employee__role="Admin")


def _get_role_and_team_lists(active_role: str | None, base_qs: QuerySet) -> tuple[list, QuerySet]:
    """
    Wyznacza dostępne listy ról oraz zespołów służące do filtrowania w zależności od roli użytkownika.
    """
    if active_role in ("Manager", "HR"):
        roles = []
        teams = Team.objects.filter(
            id__in=base_qs.values("employee__worker_profile__team")
        ).distinct()
    else:
        roles = ["Worker", "Manager", "HR"]
        teams = Team.objects.filter(is_active=True)

    return roles, teams


def _apply_report_filters(qs: QuerySet, filters: dict, all_roles_list: list) -> QuerySet:
    """
    Aplikuje zestaw filtrów (status, daty, ramy czasowe, użytkownik, zespół) do zapytania QuerySet wniosków urlopowych.
    """
    if user_id := filters["user"]:
        if str(user_id).isdigit():
            qs = qs.filter(employee_id=int(user_id))
    elif query := filters["search"]:
        qs = qs.filter(
            Q(employee__first_name__icontains=query)
            | Q(employee__last_name__icontains=query)
            | Q(employee__username__icontains=query)
        )

    if status := filters["status"]:
        if status in LeaveRequest.Status.values:
            qs = qs.filter(status=status)

    proc = filters["processed"]
    if proc == "unprocessed":
        qs = qs.filter(status="pending")
    elif proc == "processed":
        qs = qs.filter(status__in=["approved", "rejected", "canceled"])
    elif proc in ("approved", "rejected", "canceled"):
        qs = qs.filter(status=proc)

    if date_from_str := filters["date_from"]:
        try:
            date_from = datetime.strptime(date_from_str, DATE_FMT).date()
            qs = qs.filter(end_date__gte=date_from)
        except ValueError:
            pass

    if date_to_str := filters["date_to"]:
        try:
            date_to = datetime.strptime(date_to_str, DATE_FMT).date()
            qs = qs.filter(start_date__lte=date_to)
        except ValueError:
            pass

    if team_id := filters["team"]:
        if str(team_id).isdigit():
            qs = qs.filter(employee__worker_profile__team_id=int(team_id))

    return qs.order_by("-created_at")


def _get_applied_leave_filters_text(filters: dict) -> str:
    """
    Tworzy opis tekstowy przedstawiający listę nałożonych filtrów na wnioski urlopowe do zaprezentowania w raporcie.
    """
    active_filters = []

    if filters.get("status"):
        active_filters.append(f"{_('Status')}: {filters['status']}")
    if filters.get("processed"):
        active_filters.append(f"{_('Stan')}: {filters['processed']}")

    if (team_id := filters.get("team")) and str(team_id).isdigit():
        team_obj = Team.objects.filter(id=int(team_id)).first()
        team_name = team_obj.name if team_obj else team_id
        active_filters.append(f"{_('Zespół')}: {team_name}")

    if (user_id := filters.get("user")) and str(user_id).isdigit():
        user_obj = User.objects.filter(id=int(user_id)).first()
        user_name = user_obj.username if user_obj else user_id
        active_filters.append(f"{_('Użytkownik')}: {user_name}")

    if search := filters.get("search"):
        active_filters.append(f'{_("Szukaj")}: "{search}"')
    if filters.get("date_from"):
        active_filters.append(f"{_('Data od')}: {filters['date_from']}")
    if filters.get("date_to"):
        active_filters.append(f"{_('Data do')}: {filters['date_to']}")

    return ", ".join(active_filters) if active_filters else str(_("Brak (wszystkie widoczne wnioski)"))


def _leave_request_filters_from_get(request) -> dict:
    """
    Zwraca słownik zawierający parametry filtrowania wniosków urlopowych pobrane z zapytania GET.
    """
    return {
        "status": request.GET.get("status", "").lower(),
        "processed": request.GET.get("processed", "").lower(),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "team": request.GET.get("team", ""),
        "user": request.GET.get("user", ""),
        "search": request.GET.get("search", "").strip(),
    }


def _employee_team_name(employee) -> str:
    """
    Zwraca nazwę zespołu przypisanego do danego pracownika lub znak '-' w przypadku braku zespołu.
    """
    profile = getattr(employee, "worker_profile", None)
    return profile.team.name if profile and profile.team else "-"


def _confirmer_name(leave_request) -> str:
    """
    Pomocnicza funkcja formatująca i zwracająca imię oraz nazwisko (lub username) osoby zatwierdzającej lub odrzucającej wniosek urlopowy.
    """
    if not leave_request.who_confirmed:
        return "-"
    who = leave_request.who_confirmed
    return f"{who.first_name} {who.last_name}".strip() or who.username


# =========================================================================
# Widok raportu wniosków (płaska tabela z paginacją)
# =========================================================================

@login_required
@role_required("can_see_all_requests")
def leave_requests_report_list(request):
    """
    Paginowany widok listy raportu wniosków urlopowych zawierający formularze i opcje filtrów.
    """
    active_role = _get_active_role(request)
    base_qs = _base_visible_queryset(request, active_role)
    all_roles_list, all_teams_list = _get_role_and_team_lists(active_role, base_qs)

    filters = _leave_request_filters_from_get(request)
    queryset = _apply_report_filters(base_qs, filters, all_roles_list)

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "requests": page_obj.object_list,
        "active_role": active_role,
        "proc_filter": filters["processed"],
        "status_filter": filters["status"],
        "date_from": filters["date_from"],
        "date_to": filters["date_to"],
        "team_filter": filters["team"],
        "user_filter": filters["user"],
        "search_query": filters["search"],
        "all_teams_list": all_teams_list,
        "all_roles_list": all_roles_list,
        "applied_filters_text": _get_applied_leave_filters_text(filters),
    }
    return render(request, "reports/leave_requests_report_list.html", context)


# =========================================================================
# Eksporty: leave requests
# =========================================================================

@login_required
@role_required("can_see_all_requests")
def export_leave_requests_csv(request):
    """
    Eksportuje wyfiltrowane wnioski urlopowe do pliku w formacie CSV.
    """
    active_role = _get_active_role(request)
    base_qs = _base_visible_queryset(request, active_role)
    all_roles_list, _ = _get_role_and_team_lists(active_role, base_qs)

    filters = _leave_request_filters_from_get(request)
    requests_qs = _apply_report_filters(base_qs, filters, all_roles_list)

    rows = []
    for req in requests_qs:
        emp = req.employee
        emp_name = f"{emp.first_name} {emp.last_name}".strip() or emp.username

        rows.append([
            req.id,
            emp_name,
            _employee_team_name(emp),
            req.start_date.strftime(DATE_FMT) if req.start_date else "-",
            req.end_date.strftime(DATE_FMT) if req.end_date else "-",
            req.amount_days,
            req.get_status_display(),
            _confirmer_name(req),
        ])

    return _csv_response(
        _("raport_wnioskow"),
        [
            _("ID Wniosku"),
            _("Pracownik"),
            _("Zespół"),
            _("Od"),
            _("Do"),
            _("Dni"),
            _("Status"),
            _("Zatwierdził/Odrzucił"),
        ],
        rows,
    )


@login_required
@role_required("can_see_all_requests")
def export_leave_requests_pdf(request):
    """
    Generuje dokument PDF zawierający tabelę z wyfiltrowanymi wnioskami urlopowymi.
    """
    active_role = _get_active_role(request)
    base_qs = _base_visible_queryset(request, active_role)
    all_roles_list, _ = _get_role_and_team_lists(active_role, base_qs)

    filters = _leave_request_filters_from_get(request)
    requests_qs = _apply_report_filters(base_qs, filters, all_roles_list)
    filters_desc = _get_applied_leave_filters_text(filters)

    styles = _pdf_styles(cell_font_size=8, cell_leading=10)
    buffer, doc = _new_pdf_document()
    elements = []

    _add_report_header(
        elements, styles,
        title=_("Raport Wniosków Urlopowych"),
        request=request, active_role=active_role,
        filters_desc=filters_desc, record_count=requests_qs.count(),
    )

    table_rows = []
    for req in requests_qs:
        emp = req.employee
        emp_name = f"{emp.first_name} {emp.last_name}".strip() or emp.username
        table_rows.append([
            emp_name,
            _employee_team_name(emp),
            req.start_date.strftime(DATE_FMT) if req.start_date else "-",
            req.end_date.strftime(DATE_FMT) if req.end_date else "-",
            req.amount_days,
            req.get_status_display(),
            _confirmer_name(req),
        ])

    elements.append(_build_table(
        [
            _("Pracownik"),
            _("Zespół"),
            _("Od"),
            _("Do"),
            _("Dni"),
            _("Status"),
            _("Zatwierdził(a)"),
        ],
        table_rows,
        [110, 85, 65, 65, 35, 75, 100],
        styles,
    ))

    return _pdf_response(buffer, doc, elements, _("raport_wnioskow"))


# =========================================================================
# JSON API - helpery
# =========================================================================

def _json_ok(data, **extra) -> JsonResponse:
    """
    Struktura odpowiedzi: {"results": [...], ...dodatkowe_pola}.
    """
    payload = {"results": data, **extra}
    return JsonResponse(payload, encoder=DjangoJSONEncoder, safe=True)


def _paginate_for_json(request, queryset_or_list, default_page_size: int = 20) -> tuple[list, dict]:
    """
    Paginuje `queryset_or_list` za pomocą parametrów zapytania ?page= i ?page_size=.
    Zwraca (elementy_strony, metadane_paginacji). Wartość page_size jest ograniczona do maksymalnie 200,
    aby zapobiec przypadkowemu pobraniu całej tabeli w jednym zapytaniu.
    """
    try:
        page_size = min(int(request.GET.get("page_size", default_page_size)), 200)
    except ValueError:
        page_size = default_page_size

    paginator = Paginator(queryset_or_list, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    meta = {
        "page": page_obj.number,
        "num_pages": paginator.num_pages,
        "count": paginator.count,
        "page_size": page_size,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }
    return list(page_obj.object_list), meta


# =========================================================================
# JSON API - endpointy
# =========================================================================

@login_required
@role_required("can_export_requests")
def api_users_per_role(request):
    """
    Zwraca dane statystyczne o liczbie i aktywności użytkowników w podziale na role w formacie JSON.
    """
    if _manager_is_restricted(request):
        return JsonResponse({"detail": str(_("Brak dostępu dla Manager."))}, status=403)

    return _json_ok(_get_users_per_role_data())


@login_required
@role_required("can_export_requests")
def api_leave_usage(request):
    """
    Zwraca spaginowaną listę wykorzystania urlopów przez pracowników w formacie JSON z uwzględnieniem filtrów ról i zespołów.
    """
    active_role = _get_active_role(request)
    role_filter = request.GET.get("role", "ALL")
    team_filter = request.GET.get("team", "ALL")

    if active_role == "Manager":
        role_filter = "ALL"
        if team_filter == "NONE":
            team_filter = "ALL"

    profiles = _leave_usage_profiles(request, active_role)
    report_rows = _leave_usage_rows(profiles, role_filter, team_filter)

    page_items, meta = _paginate_for_json(request, report_rows)
    return _json_ok(page_items, filters={"role": role_filter, "team": team_filter}, **meta)


@login_required
@role_required("can_export_requests")
def api_team_report(request):
    """
    Zwraca spaginowane dane zbiorcze dotyczące wykorzystania urlopów w podziale na zespoły w formacie JSON.
    """
    report_rows = _team_rows(request)
    page_items, meta = _paginate_for_json(request, report_rows)
    return _json_ok(page_items, **meta)


@login_required
@role_required("can_view_logs")
def api_activity_log(request):
    """
    Zwraca przefiltrowaną i spaginowaną listę logów aktywności systemowych w formacie JSON.
    """
    filters = _activity_log_filters(request)
    logs = _filtered_activity_logs(filters)

    page_items, meta = _paginate_for_json(request, logs)
    results = [
        {
            "id": log.id,
            "created_at": dj_timezone.localtime(log.created_at) if log.created_at else None,
            "who": str(log.who) if log.who else None,
            "action": log.action,
            "action_display": log.get_action_display(),
            "object_type": log.object_type,
            "object_type_display": log.get_object_type_display(),
            "object_id": log.object_id,
            "details": log.details or "",
        }
        for log in page_items
    ]
    return _json_ok(
        results,
        filters={k: v for k, v in filters.items() if v},
        **meta,
    )


@login_required
@role_required("can_view_logs")
def api_auth_log(request):
    """
    Zwraca przefiltrowaną i spaginowaną listę logów uwierzytelniania w formacie JSON.
    """
    filters = _auth_log_filters(request)
    logs = _filtered_auth_logs(filters)

    page_items, meta = _paginate_for_json(request, logs)
    results = [
        {
            "id": log.id,
            "timestamp": dj_timezone.localtime(log.timestamp) if log.timestamp else None,
            "user": log.user.get_username() if log.user else None,
            "action": log.action,
            "action_display": log.get_action_display(),
            "severity": log.severity,
            "severity_display": log.get_severity_display(),
            "ip_address": log.ip_address or "",
            "details": log.details or "",
        }
        for log in page_items
    ]
    return _json_ok(
        results,
        filters={k: v for k, v in filters.items() if v},
        **meta,
    )


@login_required
@role_required("can_see_all_requests")
def api_leave_requests(request):
    """
    Zwraca przefiltrowaną i spaginowaną listę wniosków urlopowych w formacie JSON z opisem zastosowanych filtrów.
    """
    active_role = _get_active_role(request)
    base_qs = _base_visible_queryset(request, active_role)
    all_roles_list, _ = _get_role_and_team_lists(active_role, base_qs)

    filters = _leave_request_filters_from_get(request)
    requests_qs = _apply_report_filters(base_qs, filters, all_roles_list)

    page_items, meta = _paginate_for_json(request, requests_qs)
    results = []
    for req in page_items:
        emp = req.employee
        emp_name = f"{emp.first_name} {emp.last_name}".strip() or emp.username
        emp_role = emp.get_role_display() if hasattr(emp, "get_role_display") else emp.role

        results.append({
            "id": req.id,
            "employee": emp_name,
            "employee_role": emp_role,
            "team": _employee_team_name(emp),
            "start_date": req.start_date,
            "end_date": req.end_date,
            "amount_days": req.amount_days,
            "status": req.status,
            "status_display": req.get_status_display(),
            "confirmed_by": _confirmer_name(req),
        })

    return _json_ok(
        results,
        applied_filters=_get_applied_leave_filters_text(filters),
        **meta,
    )