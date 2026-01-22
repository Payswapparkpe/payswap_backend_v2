"""
API Version 1 Views - Internal Access
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .permissions import IsInternalUser


class HealthCheckView(APIView):
    """
    Health check endpoint for API v1 (Internal)
    """
    permission_classes = [IsInternalUser]
    
    def get(self, request):
        return Response(
            {
                "status": "healthy",
                "version": "v1",
                "access_type": "internal",
                "user": request.user.username if request.user.is_authenticated else None,
            },
            status=status.HTTP_200_OK,
        )
