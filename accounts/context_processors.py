ALLOWED_ROLES = {
    'Manager': ['Manager', 'Worker'],
    'HR': ['HR', 'Worker'],
    'Admin': ['Admin'],
    'Worker': ['Worker'],
}


def active_role(request):
    if not request.user.is_authenticated:
        return {'active_role': None, 'available_roles': []}

    return {
        'active_role': request.session.get('active_role', request.user.role),
        'available_roles': ALLOWED_ROLES.get(request.user.role, []),
    }