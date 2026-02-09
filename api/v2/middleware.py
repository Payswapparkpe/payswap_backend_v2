"""
API Version 2 Middleware
IP Whitelisting and request logging middleware
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from portal.models import APIKeyUsageLog
from portal.services.api_key_service import APIKeyService
from django.utils import timezone
import time
import json


class APIKeyIPWhitelistMiddleware(MiddlewareMixin):
    """
    Middleware to check IP whitelist for API keys
    Should be placed after authentication middleware
    """
    
    def process_request(self, request):
        """Check IP whitelist before processing request"""
        # Only check for API v2 endpoints
        if not request.path.startswith('/api/v2/'):
            return None
        
        # Check if API key is authenticated
        if not hasattr(request, 'api_key') or not request.api_key:
            return None  # Let authentication handle it
        
        api_key = request.api_key
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.META.get('REMOTE_ADDR')
        
        # Check IP whitelist
        if not api_key.is_ip_allowed(client_ip):
            return JsonResponse(
                {
                    'success': False,
                    'error': 'IP address not allowed',
                    'message': 'Your IP address is not in the whitelist for this API key'
                },
                status=403
            )
        
        return None


class APIKeyUsageLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log API key usage for analytics
    """
    
    def process_request(self, request):
        """Store request start time"""
        if request.path.startswith('/api/v2/') and hasattr(request, 'api_key'):
            request._api_request_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Log API request after response"""
        # Only log API v2 endpoints with API keys
        if not request.path.startswith('/api/v2/'):
            return response
        
        if not hasattr(request, 'api_key') or not request.api_key:
            return response
        
        try:
            api_key = request.api_key
            partner = request.partner
            
            # Calculate response time
            response_time = None
            if hasattr(request, '_api_request_start_time'):
                response_time = (time.time() - request._api_request_start_time) * 1000  # Convert to ms
            
            # Get client IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                client_ip = x_forwarded_for.split(',')[0].strip()
            else:
                client_ip = request.META.get('REMOTE_ADDR')
            
            # Get request ID
            request_id = request.META.get('HTTP_X_REQUEST_ID') or request.META.get('REQUEST_ID', '')
            
            # Get error message if response is error
            error_message = None
            if response.status_code >= 400:
                try:
                    if hasattr(response, 'data'):
                        error_message = str(response.data.get('error', response.data.get('message', '')))
                    elif hasattr(response, 'content'):
                        content = response.content.decode('utf-8')
                        try:
                            data = json.loads(content)
                            error_message = data.get('error', data.get('message', ''))
                        except:
                            error_message = content[:500]
                except:
                    pass
            
            # Create usage log
            APIKeyUsageLog.objects.create(
                api_key=api_key,
                partner=partner,
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                response_time=response_time,
                ip_address=client_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                request_id=request_id,
                error_message=error_message[:1000] if error_message else None
            )
        except Exception as e:
            # Don't fail the request if logging fails
            import logging
            logger = logging.getLogger('api.v2.middleware')
            logger.error(f'Failed to log API usage: {str(e)}')
        
        return response
