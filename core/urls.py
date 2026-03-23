"""
URL configuration for core project.
"""
from django.contrib import admin
from django.urls import path, include

admin.site.site_header = "Payswap Hub Admin"
admin.site.site_title = "Payswap Hub"
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from portal import views as portal_views

from django.views.generic.base import RedirectView as CoreRedirectView

urlpatterns = [
    # Reseller/Partner UI removed — managed via Project Management (ParkPe / Payswap)
    path("admin/partners/", CoreRedirectView.as_view(url="/dashboard/projects/", permanent=False)),
    path("admin/partners/<path:subpath>", CoreRedirectView.as_view(url="/dashboard/projects/", permanent=False)),
    # Django Admin
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("internal/", include("api.internal.urls")),  # Ops: /internal/health/
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Django Allauth URLs
    path("accounts/", include("allauth.urls")),
    # Portal URLs (no "portal" prefix)
    path("", include("portal.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
