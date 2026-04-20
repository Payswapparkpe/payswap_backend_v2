"""
Redis-backed rate limiting for public/sensitive API endpoints.
Uses Django cache (Redis). Keys are per-IP (VAPT-003: trusted-proxy aware).
"""
from rest_framework.throttling import SimpleRateThrottle
from django.core.cache import cache
from django.utils import timezone

from api.utils.client_ip import get_client_ip


def _get_client_ip(request):
    return get_client_ip(request) or "0.0.0.0"


class ConnectScanRateThrottle(SimpleRateThrottle):
    """
    Limit QR scan (GET vehicle/by-qr) per IP.
    Default: 60 requests per minute to prevent scan flooding and enumeration.
    """
    scope = "connect_scan"
    rate = "60/min"

    def get_cache_key(self, request, view):
        ip = _get_client_ip(request)
        return f"throttle_{self.scope}_{ip}"


class ConnectCallRateThrottle(SimpleRateThrottle):
    """
    Limit call initiate per IP.
    Default: 10 per minute to prevent call bombing and Kaleyra cost abuse.
    """
    scope = "connect_call"
    rate = "10/min"

    def get_cache_key(self, request, view):
        ip = _get_client_ip(request)
        return f"throttle_{self.scope}_{ip}"


class ConnectScannerVerifyThrottle(SimpleRateThrottle):
    """
    Limit scanner OTP verify attempts per IP (SEC-003: reduce brute-force window).
    Default: 30 per hour per IP.
    """
    scope = "connect_scanner_verify"
    rate = "30/hour"

    def get_cache_key(self, request, view):
        ip = _get_client_ip(request)
        return f"throttle_{self.scope}_{ip}"


class ConnectChatRateThrottle(SimpleRateThrottle):
    """
    Limit chat message POST (send) per IP — spam / abuse protection.
    Default: 30 per minute per IP. (Polling uses ConnectChatPollThrottle.)
    """
    scope = "connect_chat_send"
    rate = "30/min"

    def get_cache_key(self, request, view):
        ip = _get_client_ip(request)
        return f"throttle_{self.scope}_{ip}"


class ConnectChatPollThrottle(SimpleRateThrottle):
    """
    Limit GET message-list polling per IP — generous so ~2.5s polling never trips 429.
    Separate from POST sends (ConnectChatRateThrottle).
    Default: 180 per minute per IP.
    """
    scope = "connect_chat_poll"
    rate = "180/min"

    def get_cache_key(self, request, view):
        ip = _get_client_ip(request)
        return f"throttle_{self.scope}_{ip}"


class AuthOTPRateThrottle(SimpleRateThrottle):
    """
    Stricter limit for OTP request/verify and register send-otp (anonymous).
    Default: 20 per hour per IP to prevent SMS bombing and brute-force.
    """
    scope = "auth_otp"
    rate = "20/hour"

    def get_cache_key(self, request, view):
        ip = _get_client_ip(request)
        return f"throttle_{self.scope}_{ip}"


class AuthLoginRateThrottle(SimpleRateThrottle):
    """
    Limit login attempts per IP (anonymous).
    Default: 30 per hour per IP.
    """
    scope = "auth_login"
    rate = "30/hour"

    def get_cache_key(self, request, view):
        ip = _get_client_ip(request)
        return f"throttle_{self.scope}_{ip}"
