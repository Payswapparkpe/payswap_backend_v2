from django.urls import path
from .views import (
    PaymentGatewaysView,
    CreateOrderView,
    VerifyPaymentView,
    CashfreePaymentWebhookView,
    CashfreeWebhookRelayView,
    RegisterOrderView,
    PaymentTransactionsListView,
    PaymentTransactionDetailView,
    PaymentTransactionReceiptHtmlView,
    PaymentStatusStreamView,
    PaymentOrdersListView,
    VoucherStatementView,
)

urlpatterns = [
    path("gateways", PaymentGatewaysView.as_view(), name="parkpe-payment-gateways"),
    path("create-order/<str:gateway>", CreateOrderView.as_view(), name="parkpe-payment-create-order"),
    path("verify/<str:gateway>", VerifyPaymentView.as_view(), name="parkpe-payment-verify"),
    path("webhook/cashfree", CashfreePaymentWebhookView.as_view(), name="parkpe-payment-webhook-cashfree"),
    path("webhook/relay/cashfree", CashfreeWebhookRelayView.as_view(), name="parkpe-payment-webhook-relay-cashfree"),
    path("orders/register", RegisterOrderView.as_view(), name="parkpe-payment-orders-register"),
    path("transactions", PaymentTransactionsListView.as_view(), name="parkpe-payment-transactions"),
    path(
        "transactions/<str:transaction_id>/receipt/",
        PaymentTransactionReceiptHtmlView.as_view(),
        name="parkpe-payment-transaction-receipt",
    ),
    path("transactions/<str:transaction_id>", PaymentTransactionDetailView.as_view(), name="parkpe-payment-transaction-detail"),
    path("stream/status/<str:order_id>", PaymentStatusStreamView.as_view(), name="parkpe-payment-stream-status"),
    path("orders", PaymentOrdersListView.as_view(), name="parkpe-payment-orders"),
    path("voucher-statement", VoucherStatementView.as_view(), name="parkpe-payment-voucher-statement"),
]
