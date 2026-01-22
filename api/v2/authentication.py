"""
API Version 2 Authentication - External Parties
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class APIKeyAuthentication(BaseAuthentication):
    """
    API Key authentication for external partners
    """
    
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY') or request.META.get('HTTP_AUTHORIZATION', '').replace('Bearer ', '')
        
        if not api_key:
            return None
        
        # Validate API key
        # Customize this based on your API key storage (database, env, etc.)
        # from core.config import payswap_config
        # if api_key != payswap_config.get_external_api_key():
        #     raise AuthenticationFailed('Invalid API key')
        
        # Return (user, token) tuple
        # For now, return None to allow custom validation in permissions
        return None
    
    def authenticate_header(self, request):
        return 'X-API-Key'
