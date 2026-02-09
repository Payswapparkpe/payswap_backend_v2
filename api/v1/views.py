"""
API Version 1 Views - Internal Access
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from .permissions import IsInternalUser
from api.mixins.response_mixin import StandardResponseMixin
from api.mixins.logging_mixin import APILoggingMixin


class HealthCheckView(APILoggingMixin, StandardResponseMixin, APIView):
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


class RuntimeConfigView(StandardResponseMixin, APIView):
    """
    Dynamic API config for frontend (Parkpe / Payswap Angular).
    GET /api/v1/runtime-config/?app=parkpe returns enabled APIs with frontend_mapping
    so the client never hardcodes endpoints.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from api_management.models import APIRegistry
        app = request.query_params.get("app", "parkpe").strip().lower()
        qs = APIRegistry.objects.filter(status=APIRegistry.STATUS_ON).order_by("module_name", "api_name")
        apis = []
        for api in qs:
            mapping = api.frontend_mapping or {}
            if app and mapping.get("app") and mapping.get("app").lower() != app:
                continue
            apis.append({
                "key": mapping.get("actionKey") or api.api_name,
                "endpoint": api.endpoint,
                "method": api.http_method,
                "version": api.version,
                "frontend_mapping": mapping,
            })
        return self.success_response(
            message="Runtime config",
            data={"app": app, "apis": apis},
            request=request,
        )
