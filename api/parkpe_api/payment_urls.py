from django.urls import path
from .views import (
    PaymentGatewaysView,
    CreateOrderView,
    VerifyPaymentView,
    PaymentTransactionsListView,
    PaymentTransactionDetailView,
    PaymentOrdersListView,
    VoucherStatementView,
)

urlpatterns = [
    path("gateways", PaymentGatewaysView.as_view(), name="parkpe-payment-gateways"),
    path("create-order/<str:gateway>", CreateOrderView.as_view(), name="parkpe-payment-create-order"),
    path("verify/<str:gateway>", VerifyPaymentView.as_view(), name="parkpe-payment-verify"),
    path("transactions", PaymentTransactionsListView.as_view(), name="parkpe-payment-transactions"),
    path("transactions/<str:transaction_id>", PaymentTransactionDetailView.as_view(), name="parkpe-payment-transaction-detail"),
    path("orders", PaymentOrdersListView.as_view(), name="parkpe-payment-orders"),
    path("voucher-statement", VoucherStatementView.as_view(), name="parkpe-payment-voucher-statement"),
]
