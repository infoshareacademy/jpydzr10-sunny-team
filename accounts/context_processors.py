def active_role(request):
    return {
        'active_role': request.session.get('active_role', request.user.role if request.user.is_authenticated else None)
    }