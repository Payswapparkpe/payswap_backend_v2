"""
API Version 1 URL Configuration - Internal Access
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HealthCheckView

router = DefaultRouter()
# Register internal ViewSets here: router.register(r'resource', ViewSet, basename='resource')

urlpatterns = [
    # Internal endpoints (require authentication)
    path("health/", HealthCheckView.as_view(), name="health-check"),
    
    # Router URLs
    path("", include(router.urls)),
]
