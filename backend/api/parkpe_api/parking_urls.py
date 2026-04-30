"""Parkpe Parking API URL patterns."""
from django.urls import path

from .fastag_webhook_view import FasTagScannerWebhookView
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
    ParkingOwnerProfileView,
    ParkingOwnerRevenueView,
    ParkingOwnerSlotStatusUpdateView,
    ParkingOwnerBookingsView,
    ParkingOwnerTeamView,
    ParkingOwnerTeamDetailView,
    ParkingExitPreviewView,
    ParkingExitPayVoucherView,
    ParkingExitPayUPIView,
    ParkingExitPaymentStatusView,
    ParkingCashfreeWebhookView,
    ParkingTxPinSetView,
    ParkingTxPinVerifyView,
    ParkingFastagListView,
    ParkingFastagLinkView,
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
    path("bookings/<str:booking_ref>/exit-preview/", ParkingExitPreviewView.as_view(), name="parking-exit-preview"),
    path("bookings/<str:booking_ref>/pay-exit/voucher/", ParkingExitPayVoucherView.as_view(), name="parking-pay-exit-voucher"),
    path("bookings/<str:booking_ref>/pay-exit/upi/", ParkingExitPayUPIView.as_view(), name="parking-pay-exit-upi"),
    path("bookings/<str:booking_ref>/cancel/", ParkingBookingCancelView.as_view(), name="parking-booking-cancel"),
    path("bookings/<str:booking_ref>/ticket/resend/", ParkingTicketResendView.as_view(), name="parking-ticket-resend"),

    # Exit payment status polling
    path("exit-payments/<int:exit_payment_id>/status/", ParkingExitPaymentStatusView.as_view(), name="parking-exit-payment-status"),

    # Cashfree webhook (no auth — verified by signature)
    path("webhooks/cashfree/", ParkingCashfreeWebhookView.as_view(), name="parking-cashfree-webhook"),

    # Customer
    path("customer/history/", ParkingCustomerHistoryView.as_view(), name="parking-customer-history"),

    # Profile Transaction PIN
    path("tx-pin/set/", ParkingTxPinSetView.as_view(), name="parking-tx-pin-set"),
    path("tx-pin/verify/", ParkingTxPinVerifyView.as_view(), name="parking-tx-pin-verify"),

    # FASTag (customer)
    path("fastag/mappings/", ParkingFastagListView.as_view(), name="parking-fastag-mappings"),
    path("fastag/link/", ParkingFastagLinkView.as_view(), name="parking-fastag-link"),

    # Owner / Operator
    path("owner/locations/", ParkingOwnerLocationsView.as_view(), name="parking-owner-locations"),
    path("owner/me/", ParkingOwnerProfileView.as_view(), name="parking-owner-me"),
    path("owner/revenue/", ParkingOwnerRevenueView.as_view(), name="parking-owner-revenue"),
    path("owner/slots/<int:slot_id>/status/", ParkingOwnerSlotStatusUpdateView.as_view(), name="parking-owner-slot-status"),
    path("owner/bookings/", ParkingOwnerBookingsView.as_view(), name="parking-owner-bookings"),
    path("locations/<int:location_id>/team/", ParkingOwnerTeamView.as_view(), name="parking-owner-team"),
    path("locations/<int:location_id>/team/<int:operator_id>/", ParkingOwnerTeamDetailView.as_view(), name="parking-owner-team-detail"),
]
