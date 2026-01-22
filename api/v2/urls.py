"""
API Version 2 URL Configuration - External Parties
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HealthCheckView, PublicAPIView, PartnerAPIView

router = DefaultRouter()
# Register external ViewSets here: router.register(r'resource', ViewSet, basename='resource')

urlpatterns = [
    # Public endpoints
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("public/", PublicAPIView.as_view(), name="public-endpoint"),
    
    # Partner endpoints (require API key)
    path("partner/", PartnerAPIView.as_view(), name="partner-endpoint"),
    
    # Router URLs
    path("", include(router.urls)),
]
