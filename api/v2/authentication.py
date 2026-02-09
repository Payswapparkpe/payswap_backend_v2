"""
API Version 2 Authentication - External Parties
Validates API key via portal.services.api_key_service and attaches partner + api_key to request.
"""
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from portal.services.api_key_service import find_api_key_by_plain_key


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR") or ""


class APIKeyAuthentication(BaseAuthentication):
    """
    API Key authentication for external partners.
    Looks up key via APIKeyService; attaches request.partner and request.api_key_obj.
    """

    def authenticate(self, request):
        raw = (
            request.META.get("HTTP_X_API_KEY")
            or (request.META.get("HTTP_AUTHORIZATION") or "").replace("Bearer ", "").strip()
        )
        if not raw:
            return None

        result = find_api_key_by_plain_key(raw)
        if not result:
            raise AuthenticationFailed("Invalid or unknown API key.")
        api_key_obj, partner = result

        if not api_key_obj.is_active():
            raise AuthenticationFailed("API key is inactive or expired.")

        client_ip = get_client_ip(request)
        if not api_key_obj.is_ip_allowed(client_ip):
            raise AuthenticationFailed("IP not allowed for this API key.")

        request.partner = partner
        request.api_key_obj = api_key_obj
        return (AnonymousUser(), api_key_obj)

    def authenticate_header(self, request):
        return "X-API-Key"
