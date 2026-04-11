"""
API Version 1 URL Configuration - Internal Access
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    HealthCheckView,
    RuntimeConfigView,
    ControlOverviewView,
    ControlAPIsListView,
    ControlPartnersListView,
)
from .logging_views import LogBulkEventsView, TrackClickView

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
    # Payswap API Governance – control tower (staff only)
    path("control/overview/", ControlOverviewView.as_view(), name="control-overview"),
    path("control/apis/", ControlAPIsListView.as_view(), name="control-apis"),
    path("control/partners/", ControlPartnersListView.as_view(), name="control-partners"),
    # Frontend analytics / click tracking (dashboard may POST here)
    path("logging/track-click/", TrackClickView.as_view(), name="logging-track-click"),
    path("logging/bulk/", LogBulkEventsView.as_view(), name="logging-bulk"),
    # Router URLs
    path("", include(router.urls)),
]
