"""
API Version 2 Views - External Parties
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .permissions import IsExternalUser, HasAPIKey
from .authentication import APIKeyAuthentication
from api.mixins.response_mixin import StandardResponseMixin


class HealthCheckView(StandardResponseMixin, APIView):
    """
    Health check endpoint for API v2 (External)
    Public endpoint for external parties
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        return self.success_response(
            message="API is healthy",
            data={
                "version": "v2",
                "access_type": "external",
                "public": True,
            },
            request=request
        )


class PublicAPIView(StandardResponseMixin, APIView):
    """
    Base view for public external endpoints
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        return self.success_response(
            message="Public endpoint accessed",
            data={
                "version": "v2",
            },
            request=request
        )


class PartnerAPIView(StandardResponseMixin, APIView):
    """
    Base view for partner endpoints (requires API key)
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    
    def get(self, request):
        return self.success_response(
            message="Partner endpoint accessed",
            data={
                "version": "v2",
                "authenticated": True,
            },
            request=request
        )
