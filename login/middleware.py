# accounts/middleware.py
from django.shortcuts import redirect


class ForcePasswordChangeMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.session.get("must_change_password", False):

                path = request.path
                current_url_name = (
                    request.resolver_match.url_name
                    if request.resolver_match
                    else None
                )
                allowed_names = [
                    "first_password_change",
                    "password_change_done",
                    "logout",
                    "set_language",
                ]

                if (
                    current_url_name not in allowed_names
                    and not path.startswith("/login/first_password_change/")
                    and not path.startswith(("/static/", "/media/"))
                ):
                    return redirect("first_password_change")

        return self.get_response(request)