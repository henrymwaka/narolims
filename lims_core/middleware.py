# lims_core/middleware.py

from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser

from .signals import set_current_user


class CurrentUserMiddleware(MiddlewareMixin):
    """
    Makes request.user available to model signals.

    IMPORTANT:
    - Must NOT interfere with UI routes
    - Must tolerate unauthenticated requests
    - Must run safely before AuthenticationMiddleware
    """

    def process_request(self, request):
        """
        Store user for signals, but do not enforce anything.
        """

        # 🔓 UI routes must bypass any assumptions
        if request.path.startswith("/lims/ui/"):
            set_current_user(None)
            return None

        user = getattr(request, "user", None)

        if isinstance(user, AnonymousUser):
            set_current_user(None)
        else:
            set_current_user(user)

        return None

    def process_response(self, request, response):
        """
        Clear user after request completes.
        """
        set_current_user(None)
        return response
