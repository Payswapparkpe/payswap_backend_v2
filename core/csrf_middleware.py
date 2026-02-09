"""
Custom CSRF middleware that skips CSRF validation for /api/ requests.
Used so the ParkPe Angular app (and other API clients) can POST without a CSRF token.
Portal form submissions (same-origin) still use {% csrf_token %} and are protected.
"""
from django.middleware.csrf import CsrfViewMiddleware


class CSRFExemptAPIMiddleware(CsrfViewMiddleware):
    """Subclass of CsrfViewMiddleware that does not enforce CSRF for /api/ paths."""

    def process_view(self, request, callback, callback_args, callback_kwargs):
        if request.path.startswith("/api/"):
            return None  # Skip CSRF check for API; let the view run
        return super().process_view(request, callback, callback_args, callback_kwargs)
