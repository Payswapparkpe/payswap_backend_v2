"""
API Version 2 Views - External Parties
"""
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
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
