from django.urls import path
from .views import (
    VoucherClaimView,
    VoucherListView,
    VoucherDetailView,
    VoucherRevealPinView,
)

urlpatterns = [
    path("vouchers/claim", VoucherClaimView.as_view(), name="parkpe-voucher-claim"),
    path("vouchers", VoucherListView.as_view(), name="parkpe-voucher-list"),
    path("vouchers/<int:voucher_id>", VoucherDetailView.as_view(), name="parkpe-voucher-detail"),
    path("vouchers/<int:voucher_id>/reveal-pin", VoucherRevealPinView.as_view(), name="parkpe-voucher-reveal-pin"),
]
