"""
URL configuration for core project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from portal import views as portal_views

urlpatterns = [
    # Admin Partner Management (must be before Django admin to avoid conflict)
    path("admin/partners/", include([
        path("", portal_views.AdminResellerPartnerDashboardView.as_view(), name="admin_reseller_partner_dashboard"),
        path("list/", portal_views.AdminResellerPartnerListView.as_view(), name="admin_reseller_partner_list"),
        path("onboard/", portal_views.AdminResellerPartnerOnboardView.as_view(), name="admin_reseller_partner_onboard"),
        path("<int:partner_id>/", portal_views.AdminResellerPartnerDetailView.as_view(), name="admin_reseller_partner_detail"),
        path("<int:partner_id>/pricing/", portal_views.AdminResellerPartnerPricingView.as_view(), name="admin_reseller_partner_pricing"),
        path("<int:partner_id>/reports/", portal_views.AdminResellerPartnerReportsView.as_view(), name="admin_reseller_partner_reports"),
        path("<int:partner_id>/settlement/", portal_views.AdminResellerPartnerSettlementView.as_view(), name="admin_reseller_partner_settlement"),
        path("settlement/<int:settlement_id>/process/", portal_views.AdminResellerPartnerSettlementProcessView.as_view(), name="admin_reseller_partner_settlement_process"),
        path("<int:partner_id>/vendors/", portal_views.AdminPartnerVendorAssignmentView.as_view(), name="admin_partner_vendor_assignment"),
        path("vendors/dashboard/", portal_views.VendorManagementDashboardView.as_view(), name="admin_vendor_management_dashboard"),
        path("services/catalog/", portal_views.ServiceCatalogView.as_view(), name="admin_service_catalog"),
        path("services/assign/<str:service_code>/<int:vendor_id>/", portal_views.AssignServiceVendorToPartnersView.as_view(), name="admin_assign_service_vendor_partners"),
    ])),
    # Django Admin (must come after admin/partners/)
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
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
