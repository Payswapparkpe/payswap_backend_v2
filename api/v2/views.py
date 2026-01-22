"""
API Version 2 Views - External Parties
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .permissions import IsExternalUser, HasAPIKey


class HealthCheckView(APIView):
    """
    Health check endpoint for API v2 (External)
    Public endpoint for external parties
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response(
            {
                "status": "healthy",
                "version": "v2",
                "access_type": "external",
                "public": True,
            },
            status=status.HTTP_200_OK,
        )


class PublicAPIView(APIView):
    """
    Base view for public external endpoints
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response(
            {
                "message": "Public endpoint",
                "version": "v2",
            },
            status=status.HTTP_200_OK,
        )


class PartnerAPIView(APIView):
    """
    Base view for partner endpoints (requires API key)
    """
    permission_classes = [HasAPIKey]
    
    def get(self, request):
        return Response(
            {
                "message": "Partner endpoint",
                "version": "v2",
                "authenticated": True,
            },
            status=status.HTTP_200_OK,
        )
