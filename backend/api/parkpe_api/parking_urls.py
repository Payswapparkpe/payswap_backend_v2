"""Parkpe Parking API URL patterns."""
from django.urls import path

from .parking_views import (
    ParkingLocationListView,
    ParkingLocationDetailView,
    ParkingSlotListView,
    ParkingRateEstimateView,
    ParkingBookingCreateView,
    ParkingBookingDetailView,
    ParkingBookingEntryView,
    ParkingBookingExitView,
    ParkingBookingCancelView,
    ParkingTicketResendView,
    ParkingCustomerHistoryView,
    ParkingOwnerLocationsView,
    ParkingOwnerRevenueView,
    ParkingOwnerSlotStatusUpdateView,
    ParkingOwnerBookingsView,
)

urlpatterns = [
    # Locations
    path("locations/", ParkingLocationListView.as_view(), name="parking-location-list"),
    path("locations/<int:location_id>/", ParkingLocationDetailView.as_view(), name="parking-location-detail"),
    path("locations/<int:location_id>/slots/", ParkingSlotListView.as_view(), name="parking-slot-list"),

    # Rates
    path("rates/estimate/", ParkingRateEstimateView.as_view(), name="parking-rate-estimate"),

    # Bookings
    path("bookings/", ParkingBookingCreateView.as_view(), name="parking-booking-create"),
    path("bookings/<str:booking_ref>/", ParkingBookingDetailView.as_view(), name="parking-booking-detail"),
    path("bookings/<str:booking_ref>/entry/", ParkingBookingEntryView.as_view(), name="parking-booking-entry"),
    path("bookings/<str:booking_ref>/exit/", ParkingBookingExitView.as_view(), name="parking-booking-exit"),
    path("bookings/<str:booking_ref>/cancel/", ParkingBookingCancelView.as_view(), name="parking-booking-cancel"),
    path("bookings/<str:booking_ref>/ticket/resend/", ParkingTicketResendView.as_view(), name="parking-ticket-resend"),

    # Customer
    path("customer/history/", ParkingCustomerHistoryView.as_view(), name="parking-customer-history"),

    # Owner / Operator
    path("owner/locations/", ParkingOwnerLocationsView.as_view(), name="parking-owner-locations"),
    path("owner/revenue/", ParkingOwnerRevenueView.as_view(), name="parking-owner-revenue"),
    path("owner/slots/<int:slot_id>/status/", ParkingOwnerSlotStatusUpdateView.as_view(), name="parking-owner-slot-status"),
    path("owner/bookings/", ParkingOwnerBookingsView.as_view(), name="parking-owner-bookings"),
]
