"""
Parkpe API – dashboard summary and payment transactions.
Requires JWT (Authorization: Bearer <token>). Returns shapes expected by Angular.
ParkPe has no wallet: voucher balance only (credit on buy voucher, debit on pay with voucher).
"""
from datetime import datetime, date
from decimal import Decimal
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.config import get_cashfree_pg_credentials
from portal.models import (
    GiftVoucher,
    GiftVoucherTransaction,
    ParkPePaymentGatewayConfig,
    ParkPePaymentOrder,
    ParkPeServiceConfig,
    ParkPeVoucherTransaction,
)
from portal.services.parkpe_voucherx_bridge import (
    get_balance,
    get_parkpe_brand_id,
    credit_voucher_balance,
    debit_voucher_balance,
)
from portal.utils.encryption import decrypt_data
from portal.utils.logging_helper import get_logger

logger = get_logger(__name__)


def _json_safe(obj):
    """Return a JSON-serializable copy of a dict (datetime/date → ISO string)."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


class PaymentGatewaysView(APIView):
    """GET /api/payment/gateways – list enabled gateways for voucher purchase. defaultGateway = one marked default or first."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        configs = list(
            ParkPePaymentGatewayConfig.objects.filter(
                service_code="",
                enabled=True,
            ).order_by("-is_default_for_voucher_purchase").values("gateway", "is_default_for_voucher_purchase")
        )
        seen = set()
        gateways = []
        default_gateway = None
        for c in configs:
            g = c.get("gateway")
            if g and g not in seen:
                seen.add(g)
                gateways.append({"id": g, "name": g.capitalize()})
                if default_gateway is None:
                    default_gateway = g
        return Response({"gateways": gateways, "defaultGateway": default_gateway})


class DashboardSummaryView(APIView):
    """GET /api/dashboard/summary – returns summary for dashboard cards."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.info("parkpe_dashboard_summary", extra_data={"user_id": request.user.pk, "stub": True})
        # Stub: return zeros; can later aggregate from WalletTransaction, challans, bookings
        return Response({
            "totalSpendMonth": 0,
            "pendingChallans": 0,
            "fastagBalance": 0,
            "activeBookings": 0,
        })


def _transaction_from_voucher_txn(txn):
    """Map ParkPeVoucherTransaction to Angular Transaction shape."""
    sc = (txn.service_code or "other").strip().lower().replace(" ", "_") or "other"
    gateway = "cashfree" if sc == "voucher_purchase" else "bbps"
    return {
        "id": str(txn.pk),
        "orderId": txn.reference_id or "",
        "transactionId": txn.reference_id or str(txn.pk),
        "transactionType": sc,
        "gateway": gateway,
        "amount": float(txn.amount),
        "currency": "INR",
        "status": "success",
        "customer": {"name": "", "email": "", "phone": ""},
        "timestamp": txn.created_at.isoformat() if txn.created_at else "",
        "description": txn.description or (txn.service_code or "Voucher transaction"),
    }


class PaymentTransactionsListView(APIView):
    """GET /api/payment/transactions?limit=20&page=1&type=&status= – from ParkPeVoucherTransaction (credits/debits)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.GET.get("limit", 20)), 50)
        page = max(1, int(request.GET.get("page", 1)))
        filter_type = (request.GET.get("type") or "").strip().lower()
        filter_status = (request.GET.get("status") or "").strip().lower()
        user = request.user

        qs = ParkPeVoucherTransaction.objects.filter(user=user).order_by("-created_at")
        combined = []
        for txn in qs:
            t = _transaction_from_voucher_txn(txn)
            if filter_type and t["transactionType"] != filter_type:
                continue
            if filter_status and t["status"] != filter_status:
                continue
            combined.append(t)
        total = len(combined)
        start = (page - 1) * limit
        page_items = combined[start : start + limit]
        return Response({"transactions": page_items, "total": total})


class PaymentTransactionDetailView(APIView):
    """GET /api/payment/transactions/<transaction_id> – single transaction for receipt (order or voucher txn)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        user = request.user
        # Try payment order by order_id
        order = ParkPePaymentOrder.objects.filter(user=user, order_id=transaction_id).first()
        if order:
            status_map = {"completed": "success", "pending": "pending", "failed": "failed"}
            return Response({
                "id": str(order.pk),
                "orderId": order.order_id,
                "transactionId": order.order_id,
                "transactionType": "voucher_purchase",
                "gateway": order.gateway,
                "amount": float(order.amount),
                "currency": "INR",
                "status": status_map.get(order.status, "pending"),
                "customer": {"name": "", "email": "", "phone": ""},
                "timestamp": order.created_at.isoformat() if order.created_at else "",
                "description": "Voucher purchase",
            })
        # Try voucher transaction by pk or reference_id
        txn = ParkPeVoucherTransaction.objects.filter(user=user).filter(
            Q(pk=transaction_id) | Q(reference_id=transaction_id)
        ).first()
        if txn:
            return Response(_transaction_from_voucher_txn(txn))
        return Response(
            {"detail": "Transaction not found."},
            status=status.HTTP_404_NOT_FOUND,
        )


class PaymentOrdersListView(APIView):
    """GET /api/payment/orders?page=1&limit=20&status= – payment orders (voucher purchases) for report."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.GET.get("limit", 50)), 100)
        page = max(1, int(request.GET.get("page", 1)))
        status_filter = (request.GET.get("status") or "").strip().lower()
        user = request.user
        qs = ParkPePaymentOrder.objects.filter(user=user).order_by("-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)
        total = qs.count()
        start = (page - 1) * limit
        orders = list(qs[start : start + limit])
        orders_data = [
            {
                "id": str(o.pk),
                "orderId": o.order_id,
                "amount": float(o.amount),
                "currency": "INR",
                "gateway": o.gateway,
                "status": o.status,
                "referenceId": o.reference_id,
                "createdAt": o.created_at.isoformat() if o.created_at else "",
            }
            for o in orders
        ]
        return Response({"orders": orders_data, "total": total})


class VoucherStatementView(APIView):
    """GET /api/payment/voucher-statement?page=1&limit=50 – voucher credits/debits for report."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.GET.get("limit", 50)), 100)
        page = max(1, int(request.GET.get("page", 1)))
        user = request.user
        balance = float(get_balance(user))
        qs = ParkPeVoucherTransaction.objects.filter(user=user).order_by("-created_at")
        total = qs.count()
        start = (page - 1) * limit
        entries = list(qs[start : start + limit])
        entries_data = [
            {
                "id": str(e.pk),
                "amount": float(e.amount),
                "transactionType": e.transaction_type,
                "balanceAfter": float(e.balance_after) if e.balance_after is not None else None,
                "referenceId": e.reference_id,
                "serviceCode": e.service_code,
                "description": e.description,
                "createdAt": e.created_at.isoformat() if e.created_at else "",
            }
            for e in entries
        ]
        return Response({"entries": entries_data, "total": total, "balance": balance})


class CreateOrderView(APIView):
    """POST /api/payment/create-order/<gateway> – create PG order for voucher purchase. Body: { amount [, currency ] }."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, gateway):
        gateway = (gateway or "").strip().lower()
        if gateway != "cashfree":
            return Response(
                {"detail": "Only Cashfree PG is supported. Use gateway cashfree."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Prefer default PG for voucher purchase; else first enabled
        config = ParkPePaymentGatewayConfig.objects.filter(
            gateway=gateway,
            service_code="",
            enabled=True,
        ).order_by("-is_default_for_voucher_purchase").first()
        if not config:
            return Response(
                {"detail": "Gateway not enabled for voucher purchase."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        amount = request.data.get("amount")
        if amount is None:
            return Response({"detail": "amount is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount_decimal = Decimal(str(amount))
        except Exception:
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        if amount_decimal <= 0:
            return Response({"detail": "Amount must be positive."}, status=status.HTTP_400_BAD_REQUEST)
        currency = request.data.get("currency") or "INR"

        user = request.user
        # Get profile for customer details
        from portal.models import Profile
        profile = getattr(user, "profile", None)
        if not profile and hasattr(user, "profile_set"):
            profile = user.profile_set.first()
        # Cashfree CustomerDetails requires customer_id length >= 3
        customer_id = f"usr_{user.pk}"
        customer_phone = getattr(profile, "phone", None) or ""
        customer_email = getattr(profile, "email", None) or getattr(user, "email", None) or ""

        if gateway == "cashfree":
            try:
                from portal.services.vendors.cashfree_pg import CashfreePGClient
                import uuid
                client_id, client_secret = get_cashfree_pg_credentials()
                if not client_id or not client_secret:
                    return Response(
                        {"detail": "Cashfree PG not configured. Set CASHFREE_PG_CLIENT_ID and CASHFREE_PG_CLIENT_SECRET in .env."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                client = CashfreePGClient(client_id=client_id, client_secret=client_secret)
                order_id = f"parkpe_v_{uuid.uuid4().hex[:16]}"
                customer_details = {
                    "customer_id": customer_id,
                    "customer_phone": customer_phone or "9999999999",
                    "customer_email": customer_email or "noreply@parkpe.in",
                    "customer_name": getattr(profile, "first_name", None) or user.username or "Customer",
                }
                return_url_base = request.data.get("return_url") or request.data.get("returnUrl")
                # Cashfree does not append order_id; add it so callback page receives it after redirect
                if return_url_base:
                    parsed = urlparse(return_url_base)
                    qs = parse_qs(parsed.query, keep_blank_values=True)
                    qs["order_id"] = [order_id]
                    new_query = urlencode(qs, doseq=True)
                    return_url = urlunparse(parsed._replace(query=new_query))
                else:
                    return_url = None
                order_meta = {"return_url": return_url} if return_url else None
                result = client.create_order(
                    order_amount=float(amount_decimal),
                    order_currency=currency,
                    customer_details=customer_details,
                    order_meta=order_meta,
                    order_id=order_id,
                )
                # Cashfree may return order_id in result; use our order_id if not
                cf_order_id = (result.get("order_id") or result.get("orderId") or order_id)
                payment_session_id = result.get("payment_session_id") or result.get("paymentSessionId")
                # metadata must be JSON-serializable (no datetime objects)
                metadata_safe = {"customer_details": customer_details, "raw_response": _json_safe(result)}
                ParkPePaymentOrder.objects.create(
                    user=user,
                    amount=amount_decimal,
                    gateway=gateway,
                    order_id=cf_order_id,
                    status=ParkPePaymentOrder.PENDING,
                    metadata=metadata_safe,
                )
                return Response({
                    "orderId": cf_order_id,
                    "paymentSessionId": payment_session_id,
                    "amount": float(amount_decimal),
                    "currency": currency,
                })
            except Exception as e:
                logger.error("parkpe_create_order_cashfree_error", extra_data={"user_id": user.pk, "gateway": gateway, "error": str(e)})
                return Response(
                    {"detail": f"Failed to create order: {str(e)}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        return Response({"detail": "Unsupported gateway."}, status=status.HTTP_400_BAD_REQUEST)


class VerifyPaymentView(APIView):
    """POST /api/payment/verify/<gateway> – verify PG payment and credit ParkPe voucher balance. Body: { orderId, paymentId? }."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, gateway):
        gateway = (gateway or "").strip().lower()
        if gateway != "cashfree":
            return Response(
                {"detail": "Only Cashfree PG is supported. Use gateway cashfree."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order_id = request.data.get("orderId") or request.data.get("order_id")
        payment_id = request.data.get("paymentId") or request.data.get("payment_id")
        if not order_id:
            return Response({"detail": "orderId is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        order = ParkPePaymentOrder.objects.filter(
            user=user,
            order_id=order_id,
            gateway=gateway,
            status=ParkPePaymentOrder.PENDING,
        ).first()
        # Idempotent: if order already completed (e.g. user refreshed callback), return success
        if not order:
            completed = ParkPePaymentOrder.objects.filter(
                user=user,
                order_id=order_id,
                gateway=gateway,
                status=ParkPePaymentOrder.COMPLETED,
            ).first()
            if completed:
                balance = get_balance(user)
                return Response({
                    "success": True,
                    "message": "Order already completed.",
                    "orderId": order_id,
                    "balance": float(balance),
                })
            return Response(
                {"detail": "Order not found or already processed."},
                status=status.HTTP_404_NOT_FOUND,
            )

        verified = False
        if gateway == "cashfree":
            try:
                from portal.services.vendors.cashfree_pg import CashfreePGClient
                client_id, client_secret = get_cashfree_pg_credentials()
                if not client_id or not client_secret:
                    return Response(
                        {"detail": "Cashfree PG not configured."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                client = CashfreePGClient(client_id=client_id, client_secret=client_secret)
                # Fetch order or payments to confirm PAID
                order_data = client.get_order(order_id)
                order_status = (order_data.get("order_status") or order_data.get("orderStatus") or "").upper()
                if order_status == "PAID":
                    verified = True
                else:
                    # Try fetching payments for this order
                    payments = client.get_payment(order_id)
                    if isinstance(payments, list):
                        for p in payments:
                            if (p.get("payment_status") or p.get("paymentStatus") or "").upper() == "SUCCESS":
                                verified = True
                                break
                    elif isinstance(payments, dict) and (payments.get("payment_status") or payments.get("paymentStatus") or "").upper() == "SUCCESS":
                        verified = True
            except Exception as e:
                logger.warning("parkpe_verify_cashfree_error", extra_data={"order_id": order_id, "error": str(e)})
                return Response(
                    {"detail": f"Verification failed: {str(e)}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        if not verified:
            return Response(
                {"detail": "Payment not confirmed. Complete payment and try again."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            from django.db import transaction
            with transaction.atomic():
                order.reference_id = payment_id
                order.status = ParkPePaymentOrder.COMPLETED
                order.save(update_fields=["reference_id", "status", "updated_at"])
                credit_voucher_balance(
                    user,
                    order.amount,
                    reference_id=order_id,
                    service_code="voucher_purchase",
                    description="Voucher purchase",
                )
            balance = get_balance(user)
            return Response({
                "success": True,
                "message": "Voucher balance updated.",
                "orderId": order_id,
                "balance": float(balance),
            })
        except ValueError as e:
            logger.warning(
                "parkpe_verify_voucher_credit_failed",
                extra_data={"order_id": order_id, "user_id": user.pk, "error": str(e)},
            )
            return Response(
                {
                    "detail": "Payment received but voucher could not be issued. "
                    "Ensure PARKPE_VOUCHER_BRAND_ID is set and the VoucherX brand is onboarded and active. "
                    "Contact support with order ID: {}.".format(order_id),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.warning(
                "parkpe_verify_voucher_credit_error",
                extra_data={"order_id": order_id, "user_id": user.pk, "error": str(e)},
            )
            return Response(
                {
                    "detail": "Payment received but voucher issuance failed. Please contact support with order ID: {}.".format(
                        order_id
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class VoucherBalanceView(APIView):
    """GET /api/voucher/balance – ParkPe voucher balance (no wallet)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        balance = get_balance(request.user)
        return Response({"balance": float(balance), "currency": "INR"})


def _mask_voucher_code(code):
    """Mask voucher code as XXXX-XXXX-XXXX-<last4>. Code may be 16 chars with or without hyphens."""
    if not code:
        return "****-****-****-****"
    raw = code.replace("-", "").upper()
    if len(raw) < 4:
        return "****-****-****-****"
    return "****-****-****-" + raw[-4:]


class VoucherListView(APIView):
    """GET /api/voucher/vouchers – List customer's ParkPe vouchers (Gift Vouchers with metadata.parkpe_user_id)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        brand_id = get_parkpe_brand_id()
        if not brand_id:
            return Response({"vouchers": [], "total": 0})
        user = request.user
        qs = (
            GiftVoucher.objects.filter(
                brand_id=brand_id,
                metadata__parkpe_user_id=user.pk,
            )
            .order_by("-issued_at")
        )
        total = qs.count()
        limit = min(int(request.GET.get("limit", 50)), 100)
        page = max(1, int(request.GET.get("page", 1)))
        start = (page - 1) * limit
        vouchers = list(qs[start : start + limit])
        items = [
            {
                "id": v.id,
                "voucherCodeMasked": _mask_voucher_code(v.voucher_code),
                "referenceNumber": v.reference_number,
                "originalAmount": float(v.original_amount),
                "currentBalance": float(v.current_balance),
                "currency": v.currency or "INR",
                "status": v.status,
                "issuedAt": v.issued_at.isoformat() if v.issued_at else None,
            }
            for v in vouchers
        ]
        return Response({"vouchers": items, "total": total})


class VoucherDetailView(APIView):
    """GET /api/voucher/vouchers/<id> – Single voucher detail (code, balance, transactions). Only own vouchers."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, voucher_id):
        brand_id = get_parkpe_brand_id()
        if not brand_id:
            return Response({"detail": "Voucher service not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        user = request.user
        try:
            v = GiftVoucher.objects.get(
                id=voucher_id,
                brand_id=brand_id,
                metadata__parkpe_user_id=user.pk,
            )
        except GiftVoucher.DoesNotExist:
            return Response({"detail": "Voucher not found."}, status=status.HTTP_404_NOT_FOUND)
        # Format code for display (XXXX-XXXX-XXXX-XXXX)
        code = v.voucher_code
        if code and len(code) == 16 and "-" not in code:
            code = "-".join([code[i : i + 4] for i in range(0, 16, 4)])
        txns = (
            GiftVoucherTransaction.objects.filter(voucher=v)
            .order_by("-created_at")[:50]
        )
        txn_list = [
            {
                "id": t.id,
                "transactionType": t.transaction_type,
                "transactionAmount": float(t.transaction_amount) if t.transaction_amount is not None else None,
                "balanceBefore": float(t.balance_before),
                "balanceAfter": float(t.balance_after),
                "redemptionMethod": t.redemption_method,
                "transactionStatus": t.transaction_status,
                "transactionRef": t.transaction_ref,
                "createdAt": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txns
        ]
        return Response({
            "id": v.id,
            "voucherCode": code,
            "referenceNumber": v.reference_number,
            "originalAmount": float(v.original_amount),
            "currentBalance": float(v.current_balance),
            "currency": v.currency or "INR",
            "status": v.status,
            "issuedAt": v.issued_at.isoformat() if v.issued_at else None,
            "transactions": txn_list,
        })


class VoucherRevealPinView(APIView):
    """POST /api/voucher/vouchers/<id>/reveal-pin – Return PIN once for customer's voucher (for display/copy)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, voucher_id):
        brand_id = get_parkpe_brand_id()
        if not brand_id:
            return Response({"detail": "Voucher service not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        user = request.user
        try:
            v = GiftVoucher.objects.get(
                id=voucher_id,
                brand_id=brand_id,
                metadata__parkpe_user_id=user.pk,
            )
        except GiftVoucher.DoesNotExist:
            return Response({"detail": "Voucher not found."}, status=status.HTTP_404_NOT_FOUND)
        if not v.metadata or "encrypted_pin" not in v.metadata:
            return Response({"detail": "PIN not available for this voucher."}, status=status.HTTP_404_NOT_FOUND)
        try:
            pin = decrypt_data(v.metadata["encrypted_pin"])
        except Exception as e:
            logger.warning("parkpe_voucher_reveal_pin_failed", extra_data={"voucher_id": v.id, "error": str(e)})
            return Response({"detail": "Could not retrieve PIN."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"pin": pin})
