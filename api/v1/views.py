"""
API Version 1 Views - Internal Access
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .permissions import IsInternalUser
from api.mixins.response_mixin import StandardResponseMixin


class HealthCheckView(StandardResponseMixin, APIView):
    """
    Health check endpoint for API v1 (Internal)
    """
    permission_classes = [IsInternalUser]
    
    def get(self, request):
        return self.success_response(
            message="API is healthy",
            data={
                "version": "v1",
                "access_type": "internal",
                "user": request.user.username if request.user.is_authenticated else None,
            },
            request=request
        )
