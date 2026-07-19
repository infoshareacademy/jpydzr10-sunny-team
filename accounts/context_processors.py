ALLOWED_ROLES = {
    'Manager': ['Manager', 'Worker'],
    'HR': ['HR', 'Worker'],
    'Admin': ['Admin'],
    'Worker': ['Worker'],
}


def active_role(request):
    if not request.user.is_authenticated:
        return {'active_role': None, 'available_roles': []}

    current_active = request.session.get('active_role', request.user.role)
    all_allowed = ALLOWED_ROLES.get(request.user.role, [])
    available_roles = [r for r in all_allowed if r != current_active]

    return {
        'active_role': current_active,
        'available_roles': available_roles,
    }