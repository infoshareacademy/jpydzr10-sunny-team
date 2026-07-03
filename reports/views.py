from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from accounts.models import User

def reports_index(request):
    return render(request, 'reports/index.html')


@login_required
def users_per_role_report(request):
    active_role = request.session.get('active_role', request.user.role)

    if active_role not in ['Admin', 'Manager', 'HR']:
        return render(request, 'leaves/access_denied.html')

    role_stats = (
        User.objects
        .values('role')
        .annotate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
        )
        .order_by('role')
    )

    report_rows = []
    for row in role_stats:
        total = row['total']
        active = row['active']
        percent_active = round(active / total * 100, 1) if total else 0
        report_rows.append({
            'role': row['role'] or 'Brak roli',
            'total': total,
            'active': active,
            'percent_active': percent_active,
        })

    context = {
        'report_rows': report_rows,
    }
    return render(request, 'reports/users_per_role.html', context)