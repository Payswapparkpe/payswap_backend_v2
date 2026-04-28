"""
API Version 2 Rate Limiting
Custom throttle classes for API key-based rate limiting
"""
from rest_framework.throttling import BaseThrottle
from rest_framework.exceptions import Throttled
from django.core.cache import cache
from django.utils import timezone
from typing import Optional


def _incr_with_limit(counter_key: str, ttl_seconds: int, limit: int) -> bool:
    """
    Atomically increment cache counter with TTL and enforce limit.
    Returns True when request is allowed, False when limit exceeded.
    """
    if cache.add(counter_key, 1, timeout=ttl_seconds):
        return True
    try:
        current = cache.incr(counter_key)
    except ValueError:
        cache.set(counter_key, 1, timeout=ttl_seconds)
        current = 1
    return current <= limit


class APIKeyRateThrottle(BaseThrottle):
    """
    Rate limiting per API key
    Uses Redis cache to track request counts
    """
    
    def get_cache_key(self, request, view):
        """Generate cache key for this API key"""
        if not hasattr(request, 'api_key') or not request.api_key:
            return None
        return f"api_rate_limit:key:{request.api_key.id}"
    
    def allow_request(self, request, view):
        """Check if request is within rate limit"""
        if not hasattr(request, 'api_key') or not request.api_key:
            return True  # No API key = no rate limiting (handled by HasAPIKey permission)
        
        api_key = request.api_key
        cache_key = self.get_cache_key(request, view)
        
        if not cache_key:
            return True
        
        # Get service name from view (if specified)
        service = getattr(view, 'service_name', 'default')
        
        # Get rate limits for this service
        service_limits = api_key.rate_limit.get(service, {})
        if not service_limits:
            # Fallback to default limits
            service_limits = api_key.rate_limit.get('default', {
                'requests_per_minute': 100,
                'requests_per_hour': 1000
            })
        
        requests_per_minute = service_limits.get('requests_per_minute', 100)
        requests_per_hour = service_limits.get('requests_per_hour', 1000)
        
        # Check minute limit
        minute_key = f"{cache_key}:minute"
        if not _incr_with_limit(minute_key, ttl_seconds=60, limit=requests_per_minute):
            # Calculate wait time
            wait_seconds = 60 - (timezone.now().second)
            raise Throttled(detail=f'Rate limit exceeded. Try again in {wait_seconds} seconds.')
        
        # Check hour limit
        hour_key = f"{cache_key}:hour"
        if not _incr_with_limit(hour_key, ttl_seconds=3600, limit=requests_per_hour):
            # Calculate wait time
            wait_seconds = 3600 - (timezone.now().minute * 60 + timezone.now().second)
            raise Throttled(detail=f'Hourly rate limit exceeded. Try again in {wait_seconds // 60} minutes.')

        return True


class ServiceRateThrottle(BaseThrottle):
    """
    Rate limiting per service (across all API keys)
    Useful for protecting specific services
    """
    
    def get_cache_key(self, request, view):
        """Generate cache key for service"""
        service = getattr(view, 'service_name', 'default')
        return f"api_rate_limit:service:{service}"
    
    def allow_request(self, request, view):
        """Check if request is within service rate limit"""
        cache_key = self.get_cache_key(request, view)
        service = getattr(view, 'service_name', 'default')
        
        # Default service limits (can be configured)
        default_limits = {
            'voucher': {'requests_per_minute': 1000, 'requests_per_hour': 10000},
            'kyc': {'requests_per_minute': 500, 'requests_per_hour': 5000},
            'payment': {'requests_per_minute': 2000, 'requests_per_hour': 20000},
            'sms': {'requests_per_minute': 1000, 'requests_per_hour': 10000},
            'default': {'requests_per_minute': 500, 'requests_per_hour': 5000},
        }
        
        limits = default_limits.get(service, default_limits['default'])
        requests_per_minute = limits.get('requests_per_minute', 500)
        requests_per_hour = limits.get('requests_per_hour', 5000)
        
        # Check minute limit
        minute_key = f"{cache_key}:minute"
        if not _incr_with_limit(minute_key, ttl_seconds=60, limit=requests_per_minute):
            wait_seconds = 60 - (timezone.now().second)
            raise Throttled(detail=f'Service rate limit exceeded. Try again in {wait_seconds} seconds.')
        
        # Check hour limit
        hour_key = f"{cache_key}:hour"
        if not _incr_with_limit(hour_key, ttl_seconds=3600, limit=requests_per_hour):
            wait_seconds = 3600 - (timezone.now().minute * 60 + timezone.now().second)
            raise Throttled(detail=f'Service hourly rate limit exceeded. Try again in {wait_seconds // 60} minutes.')

        return True


class PartnerRateThrottle(BaseThrottle):
    """
    Rate limiting per partner (across all their API keys)
    """
    
    def get_cache_key(self, request, view):
        """Generate cache key for partner"""
        if not hasattr(request, 'partner') or not request.partner:
            return None
        return f"api_rate_limit:partner:{request.partner.id}"
    
    def allow_request(self, request, view):
        """Check if request is within partner rate limit"""
        if not hasattr(request, 'partner') or not request.partner:
            return True
        
        cache_key = self.get_cache_key(request, view)
        if not cache_key:
            return True
        
        # Default partner limits (can be configured per partner)
        requests_per_minute = 500
        requests_per_hour = 5000
        
        # Check minute limit
        minute_key = f"{cache_key}:minute"
        if not _incr_with_limit(minute_key, ttl_seconds=60, limit=requests_per_minute):
            wait_seconds = 60 - (timezone.now().second)
            raise Throttled(detail=f'Partner rate limit exceeded. Try again in {wait_seconds} seconds.')
        
        # Check hour limit
        hour_key = f"{cache_key}:hour"
        if not _incr_with_limit(hour_key, ttl_seconds=3600, limit=requests_per_hour):
            wait_seconds = 3600 - (timezone.now().minute * 60 + timezone.now().second)
            raise Throttled(detail=f'Partner hourly rate limit exceeded. Try again in {wait_seconds // 60} minutes.')

        return True
