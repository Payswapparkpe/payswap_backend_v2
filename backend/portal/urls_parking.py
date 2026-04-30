"""Parking Owner Hub Portal URL patterns."""
from django.urls import path
from portal.views.parking_owner_views import (
    ParkingOwnerLoginView,
    ParkingOwnerLogoutView,
    ParkingOwnerDashboardView,
    ParkingLocationDetailView,
    ParkingRevenueView,
    ParkingBookingsListView,
    ParkingVerifyEntryView,
)

urlpatterns = [
    # Auth
    path("login/", ParkingOwnerLoginView.as_view(), name="parking_owner_login"),
    path("logout/", ParkingOwnerLogoutView.as_view(), name="parking_owner_logout"),

    # Dashboard + sub-pages
    path("", ParkingOwnerDashboardView.as_view(), name="parking_owner_dashboard"),
    path("<int:location_id>/", ParkingLocationDetailView.as_view(), name="parking_location_detail"),
    path("<int:location_id>/revenue/", ParkingRevenueView.as_view(), name="parking_revenue"),
    path("<int:location_id>/bookings/", ParkingBookingsListView.as_view(), name="parking_bookings_list"),
    path("<int:location_id>/verify/", ParkingVerifyEntryView.as_view(), name="parking_verify_entry"),
]
