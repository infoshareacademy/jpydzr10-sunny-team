import csv
from datetime import datetime
import io
import json
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render

from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from accounts.permission import Permission, role_required, RoleRequiredMixin
from leaves.models import WorkerProfile
from team.models import Team

User = get_user_model()

# --- Fonty PDF ---------------------------------------------------------

FONT_PATH = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Roboto-Regular.ttf')
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont('Roboto-Regular', FONT_PATH))
    pdfmetrics.registerFont(TTFont('Roboto-Bold', FONT_PATH))
    DEFAULT_FONT = 'Roboto-Regular'
    BOLD_FONT = 'Roboto-Bold'
else:
    DEFAULT_FONT = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'


class NumberedCanvas(canvas.Canvas):
    """Canvas dopisujący do każdej strony numer w formacie 'Strona X z Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.setFont(DEFAULT_FONT, 8)
        self.setFillColor(colors.HexColor("#64748B"))
        page_text = f"Strona {self._pageNumber} z {page_count}"
        self.drawRightString(A4[0] - 30, 20, page_text)


def _get_active_role(request):
    return request.session.get('active_role', getattr(request.user, 'role', None))


def _check_report_access_manager(request):
    return _get_active_role(request) == 'Manager'


def _pdf_table_style(row_count):
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        *[(
            'BACKGROUND', (0, i), (-1, i),
            colors.HexColor('#F8FAFC') if i % 2 == 0 else colors.white
        ) for i in range(1, row_count)],
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ])


@login_required
@role_required ("can_export_requests")
def reports_index(request):
    return render(request, 'reports/index.html')


# =========================================================================
# Raport: użytkownicy per rola
# =========================================================================

def _get_users_per_role_data():
    target_roles = [
        (None, 'Brak roli'),
        ('Worker', 'Worker'),
        ('Manager', 'Manager'),
        ('HR', 'HR'),
        ('COO', 'COO'),
    ]

    allowed_role_keys = [key for key, _ in target_roles if key is not None]
    base_filter = Q(role__in=allowed_role_keys) | Q(role__isnull=True) | Q(role='')

    role_stats = (
        User.objects
        .filter(base_filter)
        .values('role')
        .annotate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
        )
    )

    stats_map = {
        row['role'] or None: {'total': row['total'], 'active': row['active']}
        for row in role_stats
    }

    report_rows = []
    for role_key, role_display in target_roles:
        if role_key is None:
            data = stats_map.get(None, {'total': 0, 'active': 0})
            empty_str_data = stats_map.get('', {'total': 0, 'active': 0})
            total = data['total'] + empty_str_data['total']
            active = data['active'] + empty_str_data['active']
        else:
            data = stats_map.get(role_key, {'total': 0, 'active': 0})
            total = data['total']
            active = data['active']

        percent_active = round(active / total * 100, 1) if total else 0.0

        report_rows.append({
            'role': role_display,
            'total': total,
            'active': active,
            'percent_active': percent_active,
        })

    return report_rows


@login_required
@role_required ("can_export_requests")
def users_per_role_report(request):
    if  _check_report_access_manager(request):
        return redirect('home')

    report_rows = _get_users_per_role_data()
    context = {
        'report_rows': report_rows,
        'chart_labels': json.dumps([row['role'] for row in report_rows]),
        'chart_data_total': json.dumps([row['total'] for row in report_rows]),
        'chart_data_active': json.dumps([row['active'] for row in report_rows]),
    }
    return render(request, 'reports/users_per_role.html', context)


@login_required
@role_required ("can_export_requests")
def export_users_per_role_csv(request):
    if  _check_report_access_manager(request):
        return redirect('home')

    report_rows = _get_users_per_role_data()

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename_date = datetime.now().strftime("%Y-%m-%d")
    response['Content-Disposition'] = f'attachment; filename="raport_role_{filename_date}.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Rola', 'Liczba użytkowników', 'Aktywni', '% aktywnych'])
    for row in report_rows:
        writer.writerow([row['role'], row['total'], row['active'], f"{row['percent_active']}%"])

    return response


from datetime import datetime


@login_required
@role_required("can_export_requests")
def export_users_per_role_pdf(request):
    if _check_report_access_manager(request):
        return redirect('home')

    active_role = _get_active_role(request)
    include_inactive = request.GET.get('include_inactive', 'true').lower() == 'true'
    report_rows = _get_users_per_role_data()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=portrait(A4),
        rightMargin=30, leftMargin=30, topMargin=35, bottomMargin=35,
    )

    elements = []
    styles = getSampleStyleSheet()

    # Style
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Normal'], fontName=BOLD_FONT,
        fontSize=16, leading=20, textColor=colors.HexColor('#1E293B'), spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        'ReportMeta', parent=styles['Normal'], fontName=DEFAULT_FONT,
        fontSize=8.5, leading=12, textColor=colors.HexColor('#475569'), spaceAfter=3,
    )
    cell_style = ParagraphStyle(
        'TableCell', parent=styles['Normal'], fontName=DEFAULT_FONT,
        fontSize=9, leading=12, textColor=colors.HexColor('#334155'),
    )
    cell_header_style = ParagraphStyle(
        'TableHeaderCell', parent=styles['Normal'], fontName=BOLD_FONT,
        fontSize=9, leading=12, textColor=colors.HexColor('#0F172A'),
    )
    chart_title_style = ParagraphStyle(
        'ChartTitle', parent=styles['Normal'], fontName=BOLD_FONT,
        fontSize=10, leading=13, textColor=colors.HexColor('#475569'),
        alignment=1, spaceAfter=10,
    )

    # 1. Tytuł raportu
    elements.append(Paragraph("Raport Użytkowników: Role", title_style))

    # 2. Metadane raportu (Imię i nazwisko, Rola, Data)
    author_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
    author_role = active_role or getattr(request.user, 'role', '-')
    generation_date = datetime.now().strftime("%d.%m.%Y %H:%M")

    elements.append(Paragraph(f"<b>Wygenerowano przez:</b> {author_name}", meta_style))
    elements.append(Paragraph(f"<b>Rola użytkownika:</b> {author_role}", meta_style))
    elements.append(Paragraph(f"<b>Data utworzenia:</b> {generation_date}", meta_style))

    elements.append(Spacer(1, 15))

    # 3. Tabela z danymi
    table_data = [[
        Paragraph("Rola", cell_header_style),
        Paragraph("Liczba użytkowników", cell_header_style),
        Paragraph("Aktywni", cell_header_style),
        Paragraph("% aktywnych", cell_header_style),
    ]]
    for row in report_rows:
        table_data.append([
            Paragraph(str(row['role']), cell_style),
            Paragraph(str(row['total']), cell_style),
            Paragraph(str(row['active']), cell_style),
            Paragraph(f"{row['percent_active']}%", cell_style),
        ])

    table = Table(table_data, colWidths=[160, 125, 125, 125], repeatRows=1)
    table.setStyle(_pdf_table_style(len(table_data)))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # 4. Wykres kołowy
    chart_info_text = (
        "* Wykres uwzględnia: Wszyscy użytkownicy (aktywni i nieaktywni)"
        if include_inactive else
        "* Wykres uwzględnia: Tylko aktywni użytkownicy"
    )
    elements.append(Paragraph(chart_info_text, chart_title_style))
    elements.append(Spacer(1, 10))

    pie_data = [row['total'] if include_inactive else row['active'] for row in report_rows]
    pie_labels = [f"{row['role']} ({val})" for row, val in zip(report_rows, pie_data)]

    drawing = Drawing(535, 180)
    pie = Pie()
    pie.x = 180
    pie.y = 0
    pie.width = 150
    pie.height = 150
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
    elements.append(drawing)

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)

    filename_date = datetime.now().strftime("%Y-%m-%d_%H%M")
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="raport_role_{filename_date}.pdf"'
    return response

def _leave_usage_profiles(request, active_role):
    profiles = WorkerProfile.objects.select_related('user', 'team').filter(user__is_active=True)

    if active_role == 'Manager':
        managed_teams = Team.get_teams_managed_by(request.user).filter(is_active=True)
        profiles = profiles.filter(team__in=managed_teams).distinct()
    else:
        active_teams = Team.objects.filter(is_active=True)
        profiles = profiles.filter(
            Q(team__in=active_teams) | Q(team__isnull=True)
        ).distinct()

    return profiles


def _get_teams_info_for_profile(profile):
    teams_dict = {}

    if profile.team and profile.team.is_active:
        teams_dict[profile.team.id] = profile.team.name

    managed_teams = list(profile.user.head_managed_teams.filter(is_active=True)) + \
        list(profile.user.co_managed_teams.filter(is_active=True))
    for team in managed_teams:
        teams_dict[team.id] = team.name

    return [{'id': tid, 'name': name} for tid, name in teams_dict.items()]


ROLE_HIERARCHY = {'COO': 1, 'HR': 2, 'Manager': 3, 'Worker': 4}


def _leave_usage_rows(profiles, role_filter=None, team_filter=None):
    rows = []
    for profile in profiles:
        role_display = getattr(profile.user, 'role', None) or '-'
        teams_list = _get_teams_info_for_profile(profile)

        if role_filter and role_filter != 'ALL' and role_display != role_filter:
            continue

        if team_filter and team_filter != 'ALL':
            if team_filter == 'NONE':
                if teams_list:
                    continue
            else:
                team_ids = [str(t['id']) for t in teams_list]
                if team_filter not in team_ids:
                    continue

        total = profile._get_total_leave_days()
        used = profile.used_leave_days
        remaining = profile.get_leave_days()
        percent_used = round(used / total * 100, 1) if total else 0.0

        rows.append({
            'profile_id': profile.id,
            'user_id': profile.user.id,
            'first_name': profile.user.first_name,
            'last_name': profile.user.last_name,
            'role': role_display,
            'role_priority': ROLE_HIERARCHY.get(role_display, 99),
            'teams': teams_list,
            'total': total,
            'used': used,
            'remaining': remaining,
            'percent_used': percent_used,
        })

    rows.sort(key=lambda x: (x['role_priority'], x['last_name'].lower(), x['first_name'].lower()))
    return rows

@login_required
@role_required ("can_export_requests")
def leave_usage_report(request):

    active_role = _get_active_role(request)
    role_filter = request.GET.get('role', 'ALL')
    team_filter = request.GET.get('team', 'ALL')

    if active_role == 'Manager':
        role_filter = 'ALL'
        if team_filter == 'NONE':
            team_filter = 'ALL'

    profiles = _leave_usage_profiles(request, active_role)
    report_rows = _leave_usage_rows(profiles, role_filter, team_filter)

    if active_role == 'Manager':
        all_teams = Team.get_teams_managed_by(request.user).filter(is_active=True).order_by('name')
        show_no_team_option = False
    else:
        all_teams = Team.objects.filter(is_active=True).order_by('name')
        show_no_team_option = True

    context = {
        'report_rows': report_rows,
        'all_roles': ['COO', 'HR', 'Manager', 'Worker'],
        'all_teams': all_teams,
        'selected_role': role_filter,
        'selected_team': team_filter,
        'show_no_team_option': show_no_team_option,
    }
    return render(request, 'reports/leave_usage.html', context)


@login_required
@role_required ("can_export_requests")
def export_leave_usage_csv(request):

    active_role = _get_active_role(request)
    role_filter = request.GET.get('role', 'ALL')
    team_filter = request.GET.get('team', 'ALL')

    profiles = _leave_usage_profiles(request, active_role)
    report_rows = _leave_usage_rows(profiles, role_filter, team_filter)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename_date = datetime.now().strftime("%Y-%m-%d")
    response['Content-Disposition'] = f'attachment; filename="raport_pracownicy_{filename_date}.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Imię', 'Nazwisko', 'Rola', 'Zespół',
        'Przydzielone dni', 'Wykorzystane dni', 'Pozostałe dni', '% wykorzystania',
    ])
    for row in report_rows:
        teams_str = ", ".join(t['name'] for t in row['teams']) if row['teams'] else '-'
        writer.writerow([
            row['first_name'], row['last_name'], row['role'], teams_str,
            row['total'], row['used'], row['remaining'], f"{row['percent_used']}%",
        ])

    return response


@login_required
@role_required("can_export_requests")
def export_leave_usage_pdf(request):
    active_role = _get_active_role(request)
    role_filter = request.GET.get('role', 'ALL')
    team_filter = request.GET.get('team', 'ALL')

    profiles = _leave_usage_profiles(request, active_role)
    report_rows = _leave_usage_rows(profiles, role_filter, team_filter)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=portrait(A4),
        rightMargin=30, leftMargin=30, topMargin=35, bottomMargin=35,
    )

    elements = []
    styles = getSampleStyleSheet()

    # Style
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Normal'], fontName=BOLD_FONT,
        fontSize=16, leading=20, textColor=colors.HexColor('#1E293B'), spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        'ReportMeta', parent=styles['Normal'], fontName=DEFAULT_FONT,
        fontSize=8.5, leading=12, textColor=colors.HexColor('#475569'), spaceAfter=3,
    )
    cell_style = ParagraphStyle(
        'TableCell', parent=styles['Normal'], fontName=DEFAULT_FONT,
        fontSize=8.5, leading=11, textColor=colors.HexColor('#334155'),
    )
    cell_header_style = ParagraphStyle(
        'TableHeaderCell', parent=styles['Normal'], fontName=BOLD_FONT,
        fontSize=8.5, leading=11, textColor=colors.HexColor('#0F172A'),
    )

    # 1. Tytuł raportu
    elements.append(Paragraph("Raport Wykorzystania Urlopów: Pracownicy", title_style))

    # 2. Wyznaczenie czytelnych nazw filtrów
    role_display_name = role_filter if role_filter != 'ALL' else 'Wszystkie'

    if team_filter == 'ALL':
        team_display_name = 'Wszystkie'
    elif team_filter == 'NONE':
        team_display_name = 'Brak zespołu'
    else:
        team_obj = Team.objects.filter(id=team_filter).first()
        team_display_name = team_obj.name if team_obj else team_filter

    # 3. Metadane raportu (Imię i nazwisko, Rola, Data, Filtry)
    author_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
    author_role = active_role or getattr(request.user, 'role', '-')
    generation_date = datetime.now().strftime("%d.%m.%Y %H:%M")

    elements.append(Paragraph(f"<b>Wygenerowano przez:</b> {author_name}", meta_style))
    elements.append(Paragraph(f"<b>Rola użytkownika:</b> {author_role}", meta_style))
    elements.append(Paragraph(f"<b>Data utworzenia:</b> {generation_date}", meta_style))
    if active_role == 'Manager':
        filters_text = f"<b>Zastosowane filtry:</b> Zespół: <i>{team_display_name}</i>"
    else:
        filters_text = f"<b>Zastosowane filtry:</b> Rola: <i>{role_display_name}</i> | Zespół: <i>{team_display_name}</i>"
    elements.append(Paragraph(filters_text, meta_style))
    elements.append(Spacer(1, 15))

    # 4. Tabela z danymi
    table_data = [[
        Paragraph("Pracownik", cell_header_style),
        Paragraph("Rola", cell_header_style),
        Paragraph("Zespół", cell_header_style),
        Paragraph("Przydzielone", cell_header_style),
        Paragraph("Wykorzystane", cell_header_style),
        Paragraph("Pozostałe", cell_header_style),
        Paragraph("% wykorzystania", cell_header_style),
    ]]

    for row in report_rows:
        full_name = f"{row['first_name']} {row['last_name']}"
        teams_pdf_html = "<br/>".join(t['name'] for t in row['teams']) if row['teams'] else "-"

        table_data.append([
            Paragraph(full_name, cell_style),
            Paragraph(str(row['role']), cell_style),
            Paragraph(teams_pdf_html, cell_style),
            Paragraph(str(row['total']), cell_style),
            Paragraph(str(row['used']), cell_style),
            Paragraph(str(row['remaining']), cell_style),
            Paragraph(f"{row['percent_used']}%", cell_style),
        ])

    table = Table(table_data, colWidths=[95, 55, 85, 65, 75, 65, 95], repeatRows=1)
    table.setStyle(_pdf_table_style(len(table_data)))
    elements.append(table)

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)

    filename_date = datetime.now().strftime("%Y-%m-%d")
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="raport_pracownicy_{filename_date}.pdf"'
    return response


# =========================================================================
# Raport: wykorzystanie urlopów per zespół
# =========================================================================

def _default_team_agg(team_id, team_name):
    return {
        'team_id': team_id,
        'team': team_name,
        'members': 0,
        'total': 0,
        'used': 0,
        'remaining': 0,
    }

def _team_rows(request):
    active_role = _get_active_role(request)
    profiles = _leave_usage_profiles(request, active_role)
    active_profiles = [p for p in profiles if getattr(p.user, 'is_active', True)]
    user_rows = _leave_usage_rows(active_profiles)

    if active_role == 'Manager':
        managed_teams = Team.get_teams_managed_by(request.user).filter(is_active=True)
        teams = {t.pk: _default_team_agg(t.pk, t.name) for t in managed_teams}
        allowed_team_ids = set(teams.keys())
    else:
        teams = {t.pk: _default_team_agg(t.pk, t.name) for t in Team.objects.filter(is_active=True)}
        allowed_team_ids = None

    for row in user_rows:
        if str(row['role']).upper() == 'MANAGER':
            continue

        teams_list = row['teams']
        if not teams_list:
            if active_role == 'Manager':
                continue
            targets = [('no_team', None, "Brak zespołu")]
        else:
            targets = [(t['id'], t['id'], t['name']) for t in teams_list]

        for team_key, team_id, team_name in targets:
            if allowed_team_ids is not None and team_key != 'no_team' and team_id not in allowed_team_ids:
                continue
            agg = teams.setdefault(team_key, _default_team_agg(team_id, team_name))
            agg['members'] += 1
            agg['total'] += row['total']
            agg['used'] += row['used']
            agg['remaining'] += row['remaining']

    report_rows = list(teams.values())
    for agg in report_rows:
        agg['percent_used'] = round(agg['used'] / agg['total'] * 100, 1) if agg['total'] else 0

    report_rows.sort(key=lambda x: str(x['team']))
    return report_rows

@login_required
@role_required ("can_export_requests")
def team_report(request):
    context = {'report_rows': _team_rows(request)}
    return render(request, 'reports/team_report.html', context)


@login_required
@role_required ("can_export_requests")
def export_team_report_csv(request):
    report_rows = _team_rows(request)

    response = HttpResponse(content_type='text/csv')
    filename_date = datetime.now().strftime("%Y-%m-%d")
    response['Content-Disposition'] = f'attachment; filename="raport_zespoly_{filename_date}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Zespół', 'Liczba osób',
        'Przydzielone dni (suma)', 'Wykorzystane dni (suma)',
        'Pozostałe dni (suma)', '% wykorzystania',
    ])
    for row in report_rows:
        writer.writerow([
            row['team'], row['members'], row['total'],
            row['used'], row['remaining'], row['percent_used'],
        ])

    return response


@login_required
@role_required ("can_export_requests")
def export_team_report_pdf(request):
    active_role = _get_active_role(request)
    report_rows = _team_rows(request)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=portrait(A4),
        rightMargin=30, leftMargin=30, topMargin=35, bottomMargin=35,
    )

    elements = []
    styles = getSampleStyleSheet()
    # Style nagłówków i tekstu
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Normal'], fontName=BOLD_FONT,
        fontSize=16, leading=20, textColor=colors.HexColor('#1E293B'), spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        'ReportMeta', parent=styles['Normal'], fontName=DEFAULT_FONT,
        fontSize=8.5, leading=12, textColor=colors.HexColor('#475569'), spaceAfter=3,
    )
    cell_style = ParagraphStyle(
        'TableCell', parent=styles['Normal'], fontName=DEFAULT_FONT,
        fontSize=8.5, leading=11, textColor=colors.HexColor('#334155'),
    )
    cell_header_style = ParagraphStyle(
        'TableHeaderCell', parent=styles['Normal'], fontName=BOLD_FONT,
        fontSize=8.5, leading=11, textColor=colors.HexColor('#0F172A'),
    )

    # 1. Tytuł raportu
    elements.append(Paragraph("Raport Wykorzystania Urlopów: Zespoły", title_style))

    # 2. Metadane (Imię i nazwisko, Rola, Data utworzenia)
    author_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
    author_role = active_role or getattr(request.user, 'role', '-')
    generation_date = datetime.now().strftime("%d.%m.%Y %H:%M")

    elements.append(Paragraph(f"<b>Wygenerowano przez:</b> {author_name}", meta_style))
    elements.append(Paragraph(f"<b>Rola użytkownika:</b> {author_role}", meta_style))
    elements.append(Paragraph(f"<b>Data utworzenia:</b> {generation_date}", meta_style))

    elements.append(Spacer(1, 15))

    # 3. Tabela z danymi zespołów
    table_data = [[
        Paragraph("Zespół", cell_header_style),
        Paragraph("Liczba osób", cell_header_style),
        Paragraph("Przydzielone (suma)", cell_header_style),
        Paragraph("Wykorzystane (suma)", cell_header_style),
        Paragraph("Pozostałe (suma)", cell_header_style),
        Paragraph("% wykorzystania", cell_header_style),
    ]]

    for row in report_rows:
        table_data.append([
            Paragraph(str(row['team']), cell_style),
            Paragraph(str(row['members']), cell_style),
            Paragraph(f"{row['total']} dni", cell_style),
            Paragraph(f"{row['used']} dni", cell_style),
            Paragraph(f"{row['remaining']} dni", cell_style),
            Paragraph(f"{row['percent_used']}%", cell_style),
        ])

    table = Table(table_data, colWidths=[110, 75, 90, 90, 75, 85], repeatRows=1)
    table.setStyle(_pdf_table_style(len(table_data)))
    elements.append(table)

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    filename_date = datetime.now().strftime("%Y-%m-%d")
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="raport_zespoly_{filename_date}.pdf"'
    return response