"""
API Version 1 URL Configuration - Internal Access
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import HealthCheckView, RuntimeConfigView

router = DefaultRouter()
# Register internal ViewSets here: router.register(r'resource', ViewSet, basename='resource')

urlpatterns = [
    # JWT for API consumers (Parkpe / Payswap Angular)
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Runtime config for Angular (no hardcoded endpoints)
    path("runtime-config/", RuntimeConfigView.as_view(), name="runtime-config"),
    # Internal endpoints (require authentication)
    path("health/", HealthCheckView.as_view(), name="health-check"),
    # Router URLs
    path("", include(router.urls)),
]
