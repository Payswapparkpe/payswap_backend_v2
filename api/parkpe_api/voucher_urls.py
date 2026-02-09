from django.urls import path
from .views import (
    VoucherBalanceView,
    VoucherListView,
    VoucherDetailView,
    VoucherRevealPinView,
)

urlpatterns = [
    path("balance", VoucherBalanceView.as_view(), name="parkpe-voucher-balance"),
    path("vouchers", VoucherListView.as_view(), name="parkpe-voucher-list"),
    path("vouchers/<int:voucher_id>", VoucherDetailView.as_view(), name="parkpe-voucher-detail"),
    path("vouchers/<int:voucher_id>/reveal-pin", VoucherRevealPinView.as_view(), name="parkpe-voucher-reveal-pin"),
]
