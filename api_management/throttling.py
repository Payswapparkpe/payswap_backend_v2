"""
Rate limiting using APIRegistry.rate_limit and optional APIKey.rate_limit.
Uses Django cache (Redis) for throttle keys.
"""
from rest_framework.throttling import SimpleRateThrottle

from .registry import get_registry_for_request


class APIRegistryThrottle(SimpleRateThrottle):
    """
    Throttle based on APIRegistry.rate_limit (e.g. {"scope": "user", "rate": "60/min"}).
    Scope can be "user", "ip", or "apikey". If no registry or no rate, no throttle is applied.
    """

    scope = "api_registry"

    def get_rate(self, request, view):
        registry = get_registry_for_request(request)
        if not registry or not registry.rate_limit:
            return None  # no throttle
        rate_config = registry.rate_limit
        if not isinstance(rate_config, dict):
            return None
        return rate_config.get("rate") or None

    def get_cache_key(self, request, view):
        registry = get_registry_for_request(request)
        if not registry or not registry.rate_limit:
            return None
        rate_config = registry.rate_limit
        if not isinstance(rate_config, dict):
            return None
        scope = rate_config.get("scope", "user")

        ident = None
        if scope == "user" and request.user and request.user.is_authenticated:
            ident = str(request.user.pk)
        elif scope == "apikey":
            api_key_obj = getattr(request, "api_key_obj", None) or getattr(
                request, "api_key", None
            )
            if api_key_obj:
                ident = f"apikey:{api_key_obj.pk}"
            else:
                ident = self.get_ident(request)
        else:
            ident = self.get_ident(request)

        if not ident:
            return None

        # Include registry pk so each API has its own rate limit bucket
        ident = f"{registry.pk}:{ident}"
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
