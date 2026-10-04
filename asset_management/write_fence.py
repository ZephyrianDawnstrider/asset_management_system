"""Application write fence for a coordinated, schema-compatible cutover."""

from django.conf import settings
from django.core.management.base import CommandError
from django.http import HttpResponse


class WriteFenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Run before sessions, authentication, CSRF, and the admin site. No
        # unsafe request reaches a view while the operator has paused writes.
        # Account GET routes can also update sessions (for example password
        # reset links), so keep account and admin routes completely closed.
        unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
        auth_route = request.path_info.startswith(("/accounts/", "/admin/"))
        if settings.ASSET_WRITES_PAUSED and (unsafe or auth_route):
            response = HttpResponse(
                "Asset writes are temporarily paused. Please retry later.",
                status=503,
                content_type="text/plain; charset=utf-8",
            )
            response["Cache-Control"] = "no-store"
            response["Retry-After"] = "120"
            return response
        return self.get_response(request)


def require_writes_unpaused():
    """Stop app-owned mutating commands before they inspect or change rows."""
    if settings.ASSET_WRITES_PAUSED:
        raise CommandError("Asset writes are paused; this command did not run.")
