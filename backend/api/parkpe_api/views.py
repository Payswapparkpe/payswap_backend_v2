"""
Parkpe API – dashboard summary and payment transactions.
Requires JWT (Authorization: Bearer <token>). Returns shapes expected by Angular.
ParkPe has no wallet: voucher balance only (credit on buy voucher, debit on pay with voucher).
"""
import base64
import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, date
from decimal import Decimal
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from django.urls import reverse

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django.contrib.auth import get_user_model
from core.config import get_cashfree_pg_credentials, get_parkpe_backend_secret
from portal.models import (
    GiftVoucher,
    GiftVoucherTransaction,
    ParkPePaymentGatewayConfig,
    ParkPePaymentOrder,
    ParkPeServiceConfig,
    ParkPeVoucherTransaction,
    Profile,
)
from portal.services.parkpe_voucherx_bridge import (
    get_parkpe_brand_id,
    credit_voucher_balance,
)
from portal.services.bbps_service import BBPSService
from portal.services.notification_service_v2 import NotificationServiceV2
from portal.services.pincode_service import fetch_by_pincode
from portal.utils.transaction_id import generate_transaction_id
from portal.utils.encryption import decrypt_data
from portal.utils.logging_helper import get_logger
from portal.utils.phone_utils import format_phone_display
from portal.utils.voucher_utils import unformat_voucher_code
from portal.services.voucher_service import VoucherService

from api.parkpe_logging import log_parkpe

logger = get_logger(__name__)
User = get_user_model()


def _parkpe_backend_authenticated(request):
    """Validate Parkpe backend service-to-service auth (PARKPE_BACKEND_SECRET)."""
    secret = get_parkpe_backend_secret()
    if not secret:
        return False
    key = (
        request.META.get("HTTP_X_PARKPE_BACKEND_KEY")
        or (request.META.get("HTTP_AUTHORIZATION") or "").replace("Bearer ", "").strip()
    )
    return key and hmac.compare_digest(key, secret)


@method_decorator(csrf_exempt, name="dispatch")
class PincodeLookupView(APIView):
    """GET /api/dashboard/pincode?pincode=110001 – Look up address by 6-digit pincode (data.gov.in). No auth required."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        pincode = (request.GET.get("pincode") or request.GET.get("pin") or "").strip()
        if not pincode:
            return Response(
                {"detail": "Query parameter 'pincode' is required (6-digit Indian pincode)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        success, err_msg, addresses = fetch_by_pincode(pincode)
        if not success:
            return Response(
                {"detail": err_msg or "Pincode lookup failed."},
                status=status.HTTP_400_BAD_REQUEST if "Invalid" in (err_msg or "") else status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            "pincode": pincode,
            "addresses": addresses,
        })


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
    """GET /api/dashboard/summary – returns summary for dashboard cards. FASTag balance from BBPS API when enabled."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        fastag_balance = 0
        try:
            try:
                bbps = BBPSService()
                result = bbps.balance_check()
                if result.get("success") and result.get("balance") is not None:
                    try:
                        fastag_balance = float(result["balance"])
                    except (TypeError, ValueError):
                        pass
            except Exception as e:
                logger.warning("parkpe_dashboard_fastag_balance_failed", extra_data={"error": str(e)})
            logger.info(
                "parkpe_dashboard_summary",
                extra_data={"user_id": request.user.pk, "fastag_balance": fastag_balance},
            )
            return Response({
                "totalSpendMonth": 0,
                "pendingChallans": 0,
                "fastagBalance": fastag_balance,
                "activeBookings": 0,
            })
        except Exception as e:
            logger.exception("parkpe_dashboard_summary_error", extra_data={"error": str(e)})
            return Response({
                "totalSpendMonth": 0,
                "pendingChallans": 0,
                "fastagBalance": 0,
                "activeBookings": 0,
            }, status=status.HTTP_200_OK)


class FastagRechargeView(APIView):
    """
    POST /api/fastag/recharge – route FASTag recharge via Mobikwik BBPS payment API.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        vehicle_number = str(body.get("vehicleNumber") or body.get("fastagId") or "").strip()
        amount = body.get("amount")
        operator_id = str(body.get("operatorId") or body.get("operatorCode") or "").strip()
        customer_name = str(body.get("customerName") or "").strip()
        customer_phone = str(body.get("customerPhone") or "").strip()

        payload = {
            "vehicleNumber": vehicle_number,
            "amount": amount,
            "operatorId": operator_id,
            "customerName": customer_name,
        }

        if not vehicle_number or amount is None:
            resp = {"detail": "vehicleNumber and amount are required."}
            log_parkpe(
                "parkpe_fastag",
                "FASTag recharge validation failed",
                False,
                request=request,
                request_method="POST",
                request_body=payload,
                response_status=400,
                response_body=resp,
                extra_data={"action": "fastag_recharge"},
            )
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError("Amount must be positive.")
        except Exception:
            resp = {"detail": "Invalid amount."}
            log_parkpe(
                "parkpe_fastag",
                "FASTag recharge invalid amount",
                False,
                request=request,
                request_method="POST",
                request_body=payload,
                response_status=400,
                response_body=resp,
                extra_data={"action": "fastag_recharge"},
            )
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)

        # Resolve FASTAG operator from request or DB default.
        if not operator_id:
            try:
                from django.db.models import Q
                from portal.models import BBPSOperator

                # FASTag naming in operator sheets/DB can vary (FASTAG, FASTag Recharge, etc.)
                op = (
                    BBPSOperator.objects.filter(is_active=True, bbps_enabled=True)
                    .filter(
                        Q(category__iexact="FASTAG")
                        | Q(category__icontains="FASTAG")
                        | Q(name__icontains="FASTAG")
                    )
                    .exclude(op__isnull=True)
                    .exclude(op__exact="")
                    .order_by("name")
                    .first()
                )
                if op and str(op.op).strip():
                    operator_id = str(op.op).strip()
            except Exception:
                operator_id = ""

        if not operator_id:
            resp = {"detail": "FASTag operator is not configured."}
            log_parkpe(
                "parkpe_fastag",
                "FASTag operator missing",
                False,
                request=request,
                request_method="POST",
                request_body=payload,
                response_status=503,
                response_body=resp,
                extra_data={"action": "fastag_recharge"},
            )
            return Response(resp, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        service = BBPSService(vendor="mobikwik")
        if not service.is_available():
            resp = {"detail": "BBPS service is not configured."}
            log_parkpe(
                "parkpe_fastag",
                "FASTag BBPS service unavailable",
                False,
                request=request,
                request_method="POST",
                request_body=payload,
                response_status=503,
                response_body=resp,
                extra_data={"action": "fastag_recharge"},
            )
            return Response(resp, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        tid = generate_transaction_id()
        extra = {
            "remitterName": customer_name or request.user.username or "ParkPe User",
            "customerMobile": customer_phone,
            "paymentAccountInfo": customer_phone or vehicle_number,
            "paymentMode": str(body.get("paymentMode") or "UPI").strip() or "UPI",
            "paymentRefID": tid,
        }
        extra = {k: v for k, v in extra.items() if v not in (None, "") or k == "remitterName"}

        result = service.pay_bill(
            operator_id=operator_id,
            customer_id=vehicle_number,
            amount=str(amount_float),
            ref_id=tid,
            subscriber_id=None,
            extra=extra,
            log_context={
                "request_id": getattr(request, "request_id", None),
                "response_id": getattr(request, "response_id", None),
                "source": "ParkPe",
                "api_name": "FASTag Recharge",
            },
        )

        if not result.get("success"):
            resp = {"detail": result.get("message") or "FASTag recharge failed."}
            log_parkpe(
                "parkpe_fastag",
                "FASTag recharge failed",
                False,
                request=request,
                request_method="POST",
                request_body=payload,
                response_status=502,
                response_body=resp,
                extra_data={
                    "action": "fastag_recharge",
                    "operator_id": operator_id,
                },
            )
            return Response(resp, status=status.HTTP_502_BAD_GATEWAY)

        txn_id = result.get("transaction_id") or tid
        response_payload = {
            "success": True,
            "orderId": tid,
            "transactionId": txn_id,
            "vehicleNumber": vehicle_number,
            "amount": amount_float,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "FASTag recharge submitted successfully.",
        }
        log_parkpe(
            "parkpe_fastag",
            "FASTag recharge success",
            True,
            request=request,
            request_method="POST",
            request_body=payload,
            response_status=200,
            response_body=response_payload,
            extra_data={"action": "fastag_recharge", "operator_id": operator_id, "transaction_id": txn_id},
        )
        return Response(response_payload)


def _transaction_from_voucher_txn(txn):
    """Map ParkPeVoucherTransaction to Angular Transaction shape."""
    sc = (txn.service_code or "other").strip().lower().replace(" ", "_") or "other"

    # Human-readable gateway per service code
    _GATEWAY_MAP = {
        "bbps": "BBPS",
        "voucher_purchase": "Cashfree",
        "rc_view": "Connect",
        "fastag": "FASTag",
        "parking": "Parking",
        "challan": "Challan",
        "rollback": "System",
    }
    gateway = _GATEWAY_MAP.get(sc, "ParkPe")

    # Human-readable descriptions per service code (fallback to stored description)
    _DESC_MAP = {
        "rc_view": "Vehicle RC data fetch",
        "fastag": "FASTag recharge",
        "parking": "Parking booking",
        "challan": "Traffic challan payment",
        "voucher_purchase": "Voucher purchase (credit)",
        "rollback": "Transaction rollback",
    }
    description = txn.description or _DESC_MAP.get(sc) or (txn.service_code or "Voucher transaction")

    if sc == "bbps" and txn.description:
        # Backfill older rows that stored biller ID in description; show biller name instead.
        try:
            from portal.models import BBPSOperator

            def _replace_biller_after_prefix(text: str, prefix: str) -> str:
                if not text.startswith(prefix):
                    return text
                remainder = text[len(prefix):].strip()
                if not remainder:
                    return text
                biller_id = remainder.split(" ", 1)[0].strip()
                op = BBPSOperator.objects.filter(biller_id=biller_id).only("name").first()
                if not op or not getattr(op, "name", None):
                    return text
                biller_name = str(op.name).strip()
                if not biller_name:
                    return text
                return re.sub(rf"\b{re.escape(biller_id)}\b", biller_name, text, count=1)

            description = _replace_biller_after_prefix(description, "BBPS pay ")
            description = _replace_biller_after_prefix(description, "BBPS rollback credit ")
        except Exception:
            pass

    out = {
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
        "description": description,
        "transactionTypeDirection": txn.transaction_type,  # 'credit' | 'debit'
    }
    if txn.balance_after is not None:
        out["balanceAfter"] = float(txn.balance_after)
    return out


def _parse_date_param(value):
    """Parse ISO date string (YYYY-MM-DD) to date; return None if invalid or empty."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _transaction_from_payment_order(order):
    """Map ParkPePaymentOrder to Angular Transaction shape (voucher purchases)."""
    status_map = {"completed": "success", "pending": "pending", "failed": "failed"}
    return {
        "id": order.order_id,           # Use order_id consistently (list + detail)
        "orderId": order.order_id,
        "transactionId": order.order_id,
        "transactionType": "voucher_purchase",
        "gateway": "Cashfree",
        "amount": float(order.amount),
        "currency": "INR",
        "status": status_map.get(order.status, "pending"),
        "customer": {"name": "", "email": "", "phone": ""},
        "timestamp": order.created_at.isoformat() if order.created_at else "",
        "description": "Voucher purchase",
        "transactionTypeDirection": "credit",
    }


class PaymentTransactionsListView(APIView):
    """GET /api/payment/transactions – from ParkPeVoucherTransaction + ParkPePaymentOrder (merged, sorted by date)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.GET.get("limit", 20)), 50)
        page = max(1, int(request.GET.get("page", 1)))
        filter_type = (request.GET.get("type") or "").strip().lower()
        filter_status = (request.GET.get("status") or "").strip().lower()
        date_from = _parse_date_param(request.GET.get("date_from"))
        date_to = _parse_date_param(request.GET.get("date_to"))
        user = request.user

        # Refresh pending Cashfree orders from PG so history does not stay stuck on "pending"
        # (callback/webhook may have been missed; Celery may not be running on small deploys).
        try:
            if ParkPePaymentOrder.objects.filter(
                user=user,
                gateway="cashfree",
                status=ParkPePaymentOrder.PENDING,
            ).exists():
                reconcile_pending_cashfree_orders(
                    limit=25,
                    min_age_minutes=0,
                    max_age_hours=72,
                    user_id=user.pk,
                )
        except Exception as e:
            logger.warning(
                "parkpe_transactions_list_reconcile_failed",
                extra_data={"user_id": user.pk, "error": str(e)[:200]},
            )

        # 1. Voucher transactions (BBPS/Connect debits, rollback credits, etc.)
        qs_txn = ParkPeVoucherTransaction.objects.filter(user=user).order_by("-created_at")
        if date_from is not None:
            qs_txn = qs_txn.filter(created_at__date__gte=date_from)
        if date_to is not None:
            qs_txn = qs_txn.filter(created_at__date__lte=date_to)

        # 2. Payment orders (voucher purchases – so they show in history even before voucher credit)
        qs_orders = ParkPePaymentOrder.objects.filter(user=user).order_by("-created_at")
        if date_from is not None:
            qs_orders = qs_orders.filter(created_at__date__gte=date_from)
        if date_to is not None:
            qs_orders = qs_orders.filter(created_at__date__lte=date_to)

        # 3. Merge: list of (timestamp, payload) then sort by timestamp desc
        combined_raw = []
        for txn in qs_txn:
            t = _transaction_from_voucher_txn(txn)
            ts = txn.created_at
            combined_raw.append((ts, t))
        for order in qs_orders:
            t = _transaction_from_payment_order(order)
            ts = order.created_at
            combined_raw.append((ts, t))

        combined_raw.sort(key=lambda x: x[0], reverse=True)
        combined = [t for _, t in combined_raw]

        # 4. Deduplicate: same order_id can appear as both order and (later) voucher credit – keep one (prefer voucher txn for consistency)
        seen_ids = set()
        deduped = []
        for t in combined:
            tid = t.get("transactionId") or t.get("id")
            if tid in seen_ids:
                continue
            seen_ids.add(tid)
            if filter_type and t.get("transactionType") != filter_type:
                continue
            if filter_status and t.get("status") != filter_status:
                continue
            deduped.append(t)

        total = len(deduped)
        start = (page - 1) * limit
        page_items = deduped[start : start + limit]
        return Response({"transactions": page_items, "total": total})


class PaymentTransactionDetailView(APIView):
    """GET /api/payment/transactions/<transaction_id> – single transaction for receipt (order or voucher txn)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        user = request.user
        try:
            if ParkPePaymentOrder.objects.filter(
                user=user,
                order_id=transaction_id,
                gateway="cashfree",
                status=ParkPePaymentOrder.PENDING,
            ).exists():
                reconcile_pending_cashfree_orders(
                    limit=5,
                    min_age_minutes=0,
                    max_age_hours=72,
                    order_ids=[transaction_id],
                    user_id=user.pk,
                )
        except Exception as e:
            logger.warning(
                "parkpe_transaction_detail_reconcile_failed",
                extra_data={"user_id": user.pk, "transaction_id": transaction_id, "error": str(e)[:200]},
            )
        # Try payment order by order_id
        order = ParkPePaymentOrder.objects.filter(user=user, order_id=transaction_id).first()
        if order:
            status_map = {"completed": "success", "pending": "pending", "failed": "failed"}
            return Response({
                "id": order.order_id,           # Consistent with list
                "orderId": order.order_id,
                "transactionId": order.order_id,
                "transactionType": "voucher_purchase",
                "gateway": "Cashfree",
                "amount": float(order.amount),
                "currency": "INR",
                "status": status_map.get(order.status, "pending"),
                "customer": {"name": "", "email": "", "phone": ""},
                "timestamp": order.created_at.isoformat() if order.created_at else "",
                "description": "Voucher purchase",
                "transactionTypeDirection": "credit",
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

        try:
            if ParkPePaymentOrder.objects.filter(
                user=user,
                gateway="cashfree",
                status=ParkPePaymentOrder.PENDING,
            ).exists():
                reconcile_pending_cashfree_orders(
                    limit=25,
                    min_age_minutes=0,
                    max_age_hours=72,
                    user_id=user.pk,
                )
        except Exception as e:
            logger.warning(
                "parkpe_orders_list_reconcile_failed",
                extra_data={"user_id": user.pk, "error": str(e)[:200]},
            )

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
        return Response({"entries": entries_data, "total": total})


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
                client_id, client_secret = get_cashfree_pg_credentials()
                if not client_id or not client_secret:
                    return Response(
                        {"detail": "Cashfree PG not configured. Set CASHFREE_PG_CLIENT_ID and CASHFREE_PG_CLIENT_SECRET in .env."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                client = CashfreePGClient(client_id=client_id, client_secret=client_secret)
                order_id = generate_transaction_id()
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
                # Webhook URL for Cashfree to notify payment success/failure (so we can update order status)
                notify_url = request.build_absolute_uri(reverse("parkpe-payment-webhook-cashfree"))
                order_meta = {"notify_url": notify_url}
                if return_url:
                    order_meta["return_url"] = return_url
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
                log_parkpe("parkpe_voucher", "Create order", True, request, {"order_id": cf_order_id, "amount": float(amount_decimal)})
                return Response({
                    "orderId": cf_order_id,
                    "paymentSessionId": payment_session_id,
                    "amount": float(amount_decimal),
                    "currency": currency,
                })
            except Exception as e:
                logger.error("parkpe_create_order_cashfree_error", extra_data={"user_id": user.pk, "gateway": gateway, "error": str(e)})
                log_parkpe("parkpe_voucher", "Create order failed", False, request, {"gateway": gateway, "error": str(e)[:200]})
                return Response(
                    {"detail": f"Failed to create order: {str(e)}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        return Response({"detail": "Unsupported gateway."}, status=status.HTTP_400_BAD_REQUEST)


def _complete_parkpe_payment_order(order, payment_id=None, request=None):
    """
    Mark order completed, credit voucher balance, send confirmation email.
    Used by VerifyPaymentView and Cashfree webhook. Caller must hold order for current gateway.
    Uses SELECT FOR UPDATE so concurrent webhook + verify cannot double-credit the same PG payment.
    """
    from django.db import transaction
    order_id = order.order_id
    with transaction.atomic():
        locked = (
            ParkPePaymentOrder.objects.select_for_update()
            .filter(pk=order.pk, status=ParkPePaymentOrder.PENDING)
            .first()
        )
        if not locked:
            return
        user = locked.user
        locked.reference_id = payment_id or locked.reference_id
        locked.status = ParkPePaymentOrder.COMPLETED
        locked.save(update_fields=["reference_id", "status", "updated_at"])
        credit_voucher_balance(
            user,
            locked.amount,
            reference_id=order_id,
            service_code="voucher_purchase",
            description="Voucher purchase",
        )
    profile = getattr(user, "profile", None)
    to_email = (getattr(profile, "email", None) or "").strip() if profile else ""
    if not to_email:
        to_email = (getattr(user, "email", None) or "").strip()
    if to_email:
        try:
            first_name = ((getattr(profile, "first_name", None) or "").strip() or "Customer") if profile else "Customer"
            NotificationServiceV2.send_email(
                to_email=to_email,
                subject="Your new ParkPe voucher has been issued",
                template_name="portal/emails/voucher_purchase_confirmation.html",
                context={
                    "first_name": first_name,
                    "amount": float(order.amount),
                    "order_id": order_id,
                    "currency": "INR",
                },
                user_id=user.pk,
                async_send=True,
                use_parkpe=True,
            )
        except Exception as mail_err:
            logger.warning(
                "parkpe_verify_voucher_email_failed",
                extra_data={"order_id": order_id, "user_id": user.pk, "error": str(mail_err)},
            )
    if request:
        log_parkpe("parkpe_voucher", "Verify payment success", True, request, {"order_id": order_id})


def reconcile_pending_cashfree_orders(
    *,
    limit: int = 200,
    min_age_minutes: int = 2,
    max_age_hours: int = 48,
    order_ids: list[str] | None = None,
    user_id: int | None = None,
) -> dict:
    """
    Recheck pending ParkPe Cashfree orders and update status.
    Returns counters for monitoring/ops.
    """
    from django.utils import timezone
    from datetime import timedelta
    from portal.services.vendors.cashfree_pg import CashfreePGClient

    counters = {
        "checked": 0,
        "completed": 0,
        "failed": 0,
        "still_pending": 0,
        "errors": 0,
    }
    now = timezone.now()
    limit = max(1, min(int(limit or 200), 1000))
    min_age = max(0, int(min_age_minutes or 0))
    max_age = max(1, int(max_age_hours or 48))
    cutoff_new = now - timedelta(minutes=min_age)
    cutoff_old = now - timedelta(hours=max_age)

    qs = ParkPePaymentOrder.objects.filter(
        gateway="cashfree",
        status=ParkPePaymentOrder.PENDING,
        created_at__lte=cutoff_new,
        created_at__gte=cutoff_old,
    ).order_by("created_at")
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if order_ids:
        clean_ids = [str(x).strip() for x in order_ids if str(x).strip()]
        if clean_ids:
            qs = qs.filter(order_id__in=clean_ids)
    pending_orders = list(qs[:limit])
    if not pending_orders:
        return counters

    client_id, client_secret = get_cashfree_pg_credentials()
    if not client_id or not client_secret:
        counters["errors"] = len(pending_orders)
        logger.warning("parkpe_pending_reconcile_skipped_missing_cashfree_credentials")
        return counters
    client = CashfreePGClient(client_id=client_id, client_secret=client_secret)

    terminal_order_statuses = {"CANCELLED", "EXPIRED", "TERMINAL_FAILED"}
    failed_payment_statuses = {"FAILED", "USER_DROPPED"}
    success_payment_statuses = {"SUCCESS"}

    for order in pending_orders:
        counters["checked"] += 1
        try:
            order_data = client.get_order(order.order_id)
            order_status = (order_data.get("order_status") or order_data.get("orderStatus") or "").upper()
            payments = client.get_payment(order.order_id)
            pay_list = (
                payments
                if isinstance(payments, list)
                else ([payments] if isinstance(payments, dict) and payments else [])
            )

            success_payment_id = ""
            for p in pay_list:
                p_status = (p.get("payment_status") or p.get("paymentStatus") or "").upper()
                if p_status in success_payment_statuses:
                    success_payment_id = (p.get("cf_payment_id") or p.get("payment_id") or "").strip()
                    break

            if order_status == "PAID" or success_payment_id:
                try:
                    _complete_parkpe_payment_order(order, payment_id=success_payment_id or None, request=None)
                    counters["completed"] += 1
                    continue
                except ValueError:
                    # Payment succeeded but voucher credit failed (brand/setup issue). Keep pending for retry after fix.
                    counters["still_pending"] += 1
                    logger.warning(
                        "parkpe_pending_reconcile_credit_failed",
                        extra_data={"order_id": order.order_id, "user_id": order.user_id},
                    )
                    continue

            if order_status in terminal_order_statuses:
                ParkPePaymentOrder.objects.filter(pk=order.pk, status=ParkPePaymentOrder.PENDING).update(
                    status=ParkPePaymentOrder.FAILED
                )
                counters["failed"] += 1
                continue

            if pay_list:
                all_failed = all(
                    ((p.get("payment_status") or p.get("paymentStatus") or "").upper() in failed_payment_statuses)
                    for p in pay_list
                )
                if all_failed:
                    ParkPePaymentOrder.objects.filter(pk=order.pk, status=ParkPePaymentOrder.PENDING).update(
                        status=ParkPePaymentOrder.FAILED
                    )
                    counters["failed"] += 1
                    continue

            counters["still_pending"] += 1
        except Exception as e:
            counters["errors"] += 1
            logger.warning(
                "parkpe_pending_reconcile_error",
                extra_data={"order_id": order.order_id, "error": str(e)[:200]},
            )

    return counters


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
        payment_id = (
            request.data.get("paymentId")
            or request.data.get("payment_id")
            or request.data.get("cf_payment_id")
        )
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
                log_parkpe("parkpe_voucher", "Verify payment (already completed)", True, request, {"order_id": order_id})
                return Response({
                    "success": True,
                    "message": "Order already completed.",
                    "orderId": order_id,
                    "transactionId": order_id,
                    "gatewayPaymentId": completed.reference_id or "",
                    "amount": float(completed.amount),
                })
            log_parkpe("parkpe_voucher", "Verify payment order not found", False, request, {"order_id": order_id})
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

                    # PG returned a terminal failure: mark order as failed so it shows Failed (not Pending)
                    if not verified:
                        terminal_order_statuses = ("CANCELLED", "EXPIRED", "TERMINAL_FAILED")
                        if order_status in terminal_order_statuses:
                            order.status = ParkPePaymentOrder.FAILED
                            order.save(update_fields=["status", "updated_at"])
                            log_parkpe("parkpe_voucher", "Verify payment order failed (PG terminal)", False, request, {"order_id": order_id, "order_status": order_status})
                            return Response(
                                {"detail": "Payment failed or was cancelled."},
                                status=status.HTTP_402_PAYMENT_REQUIRED,
                            )
                        # Check payments: if we have at least one and all are FAILED/USER_DROPPED, mark failed
                        failed_statuses = ("FAILED", "USER_DROPPED")
                        pay_list = payments if isinstance(payments, list) else ([payments] if isinstance(payments, dict) and payments else [])
                        if pay_list:
                            all_failed = all(
                                (p.get("payment_status") or p.get("paymentStatus") or "").upper() in failed_statuses
                                for p in pay_list
                            )
                            if all_failed:
                                order.status = ParkPePaymentOrder.FAILED
                                order.save(update_fields=["status", "updated_at"])
                                log_parkpe("parkpe_voucher", "Verify payment failed (PG)", False, request, {"order_id": order_id})
                                return Response(
                                    {"detail": "Payment failed. Please try again."},
                                    status=status.HTTP_402_PAYMENT_REQUIRED,
                                )
            except Exception as e:
                logger.warning("parkpe_verify_cashfree_error", extra_data={"order_id": order_id, "error": str(e)})
                log_parkpe("parkpe_voucher", "Verify payment failed", False, request, {"order_id": order_id, "error": str(e)[:200]})
                return Response(
                    {"detail": f"Verification failed: {str(e)}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        if not verified:
            log_parkpe("parkpe_voucher", "Verify payment not confirmed", False, request, {"order_id": order_id})
            return Response(
                {"detail": "Payment not confirmed. Complete payment and try again."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            _complete_parkpe_payment_order(order, payment_id=payment_id, request=request)
            order.refresh_from_db()
            return Response({
                "success": True,
                "message": "Voucher issued successfully.",
                "orderId": order_id,
                "transactionId": order_id,
                "gatewayPaymentId": order.reference_id or (payment_id or ""),
                "amount": float(order.amount),
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


def _verify_cashfree_webhook_signature(raw_body: str, signature: str, timestamp: str, client_secret: str) -> bool:
    """Verify Cashfree webhook: signedPayload = timestamp + raw_body, signature = base64(hmac-sha256(signedPayload, secret))."""
    if not raw_body or not signature or not timestamp or not client_secret:
        return False
    try:
        signed_payload = timestamp + raw_body
        expected = base64.b64encode(
            hmac.new(client_secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


@method_decorator(csrf_exempt, name="dispatch")
class CashfreePaymentWebhookView(APIView):
    """
    POST /api/payment/webhook/cashfree – Cashfree PG webhook for payment status.
    No JWT; verification via x-webhook-signature and x-webhook-timestamp.
    Updates ParkPePaymentOrder (failed/pending → failed; pending → completed on success).
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        raw_body = request.body
        try:
            body_str = raw_body.decode("utf-8")
        except Exception:
            return Response({"detail": "Invalid encoding."}, status=status.HTTP_400_BAD_REQUEST)
        signature = request.headers.get("x-webhook-signature") or request.headers.get("X-Webhook-Signature")
        timestamp = request.headers.get("x-webhook-timestamp") or request.headers.get("X-Webhook-Timestamp")
        client_id, client_secret = get_cashfree_pg_credentials()
        if not client_secret or not _verify_cashfree_webhook_signature(body_str, signature or "", timestamp or "", client_secret):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError:
            return Response({"detail": "Invalid JSON."}, status=status.HTTP_400_BAD_REQUEST)
        event_type = payload.get("type") or ""
        data = payload.get("data") or {}
        order_info = data.get("order") or {}
        order_id = order_info.get("order_id") or data.get("order_id")
        if not order_id:
            return Response({"detail": "Missing order_id."}, status=status.HTTP_400_BAD_REQUEST)

        if event_type == "PAYMENT_SUCCESS_WEBHOOK":
            order = ParkPePaymentOrder.objects.filter(
                order_id=order_id,
                gateway="cashfree",
                status=ParkPePaymentOrder.PENDING,
            ).first()
            if order:
                payment_info = data.get("payment") or {}
                cf_payment_id = payment_info.get("cf_payment_id") or payment_info.get("payment_id")
                try:
                    _complete_parkpe_payment_order(order, payment_id=cf_payment_id, request=None)
                except ValueError:
                    logger.warning(
                        "parkpe_webhook_voucher_credit_failed",
                        extra_data={"order_id": order_id, "user_id": order.user_id},
                    )
                except Exception as e:
                    logger.warning(
                        "parkpe_webhook_complete_error",
                        extra_data={"order_id": order_id, "error": str(e)},
                    )

        elif event_type in ("PAYMENT_FAILED_WEBHOOK", "PAYMENT_USER_DROPPED_WEBHOOK"):
            updated = ParkPePaymentOrder.objects.filter(
                order_id=order_id,
                gateway="cashfree",
                status=ParkPePaymentOrder.PENDING,
            ).update(status=ParkPePaymentOrder.FAILED)
            if updated:
                logger.info("parkpe_webhook_order_marked_failed", extra_data={"order_id": order_id})

        return Response(status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class RegisterOrderView(APIView):
    """
    POST /api/payment/orders/register – Parkpe backend registers a PG order created from Parkpe (PG whitelist flow).
    Auth: X-Parkpe-Backend-Key or Authorization: Bearer <PARKPE_BACKEND_SECRET>.
    Body: order_id, user_id (Hub user pk), amount, currency (optional), gateway (default cashfree), metadata (optional).
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not _parkpe_backend_authenticated(request):
            return Response(
                {"detail": "Invalid or missing Parkpe backend authentication."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        order_id = (request.data.get("order_id") or request.data.get("orderId") or "").strip()
        user_id = request.data.get("user_id")
        amount = request.data.get("amount")
        currency = request.data.get("currency") or "INR"
        gateway = (request.data.get("gateway") or "cashfree").strip().lower()
        metadata = request.data.get("metadata")
        if not order_id:
            return Response({"detail": "order_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if user_id is None:
            return Response({"detail": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if amount is None:
            return Response({"detail": "amount is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount_decimal = Decimal(str(amount))
        except Exception:
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        if amount_decimal <= 0:
            return Response({"detail": "Amount must be positive."}, status=status.HTTP_400_BAD_REQUEST)
        if gateway != "cashfree":
            return Response({"detail": "Only gateway cashfree is supported."}, status=status.HTTP_400_BAD_REQUEST)
        if ParkPePaymentOrder.objects.filter(order_id=order_id, gateway=gateway).exists():
            return Response({"detail": "Order already registered."}, status=status.HTTP_409_CONFLICT)
        metadata_safe = dict(metadata) if isinstance(metadata, dict) else {}
        ParkPePaymentOrder.objects.create(
            user=user,
            amount=amount_decimal,
            gateway=gateway,
            order_id=order_id,
            status=ParkPePaymentOrder.PENDING,
            metadata=metadata_safe,
        )
        logger.info(
            "parkpe_register_order",
            extra_data={"order_id": order_id, "user_id": user.pk, "amount": float(amount_decimal)},
        )
        return Response({"order_id": order_id, "status": "registered"}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class CashfreeWebhookRelayView(APIView):
    """
    POST /api/payment/webhook/relay/cashfree – Parkpe backend forwards Cashfree webhook (PG whitelist flow).
    Auth: X-Parkpe-Backend-Key or Authorization: Bearer <PARKPE_BACKEND_SECRET>.
    Body: raw Cashfree webhook JSON. Headers x-webhook-signature and x-webhook-timestamp must be forwarded for Hub to verify.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not _parkpe_backend_authenticated(request):
            return Response(
                {"detail": "Invalid or missing Parkpe backend authentication."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        raw_body = request.body
        try:
            body_str = raw_body.decode("utf-8")
        except Exception:
            return Response({"detail": "Invalid encoding."}, status=status.HTTP_400_BAD_REQUEST)
        signature = request.headers.get("x-webhook-signature") or request.headers.get("X-Webhook-Signature")
        timestamp = request.headers.get("x-webhook-timestamp") or request.headers.get("X-Webhook-Timestamp")
        client_id, client_secret = get_cashfree_pg_credentials()
        if not client_secret or not _verify_cashfree_webhook_signature(
            body_str, signature or "", timestamp or "", client_secret
        ):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError:
            return Response({"detail": "Invalid JSON."}, status=status.HTTP_400_BAD_REQUEST)
        event_type = payload.get("type") or ""
        data = payload.get("data") or {}
        order_info = data.get("order") or {}
        order_id = order_info.get("order_id") or data.get("order_id")
        if not order_id:
            return Response({"detail": "Missing order_id."}, status=status.HTTP_400_BAD_REQUEST)
        if event_type == "PAYMENT_SUCCESS_WEBHOOK":
            order = ParkPePaymentOrder.objects.filter(
                order_id=order_id,
                gateway="cashfree",
                status=ParkPePaymentOrder.PENDING,
            ).first()
            if order:
                payment_info = data.get("payment") or {}
                cf_payment_id = payment_info.get("cf_payment_id") or payment_info.get("payment_id")
                try:
                    _complete_parkpe_payment_order(order, payment_id=cf_payment_id, request=None)
                except (ValueError, Exception) as e:
                    logger.warning(
                        "parkpe_webhook_relay_complete_error",
                        extra_data={"order_id": order_id, "error": str(e)},
                    )
        elif event_type in ("PAYMENT_FAILED_WEBHOOK", "PAYMENT_USER_DROPPED_WEBHOOK"):
            ParkPePaymentOrder.objects.filter(
                order_id=order_id,
                gateway="cashfree",
                status=ParkPePaymentOrder.PENDING,
            ).update(status=ParkPePaymentOrder.FAILED)
        return Response(status=status.HTTP_200_OK)


def _mask_voucher_code(code):
    """Mask voucher code as XXXX-XXXX-XXXX-<last4>. Code may be 16 chars with or without hyphens."""
    if not code:
        return "****-****-****-****"
    raw = code.replace("-", "").upper()
    if len(raw) < 4:
        return "****-****-****-****"
    return "****-****-****-" + raw[-4:]


def _phone_display_map_for_user_ids(user_ids):
    """user_id -> formatted phone for display. Skips invalid ids."""
    if not user_ids:
        return {}
    uid_set = set()
    for raw in user_ids:
        try:
            uid_set.add(int(raw))
        except (TypeError, ValueError):
            continue
    if not uid_set:
        return {}
    out = {}
    for prof in Profile.objects.filter(user_id__in=uid_set).only("user_id", "phone"):
        if prof.phone:
            disp = format_phone_display(prof.phone) or prof.phone
            if disp:
                out[prof.user_id] = disp
    return out


def _parkpe_linked_fields(metadata, phone_by_user_id=None):
    """
    ParkPe link row for API: metadata.parkpe_user_id -> linked user's profile phone.
    Returns (parkpe_linked: bool, linked_user_phone: str | None).
    """
    meta = metadata or {}
    raw = meta.get("parkpe_user_id")
    if raw is None:
        return False, None
    try:
        uid = int(raw)
    except (TypeError, ValueError):
        return True, None
    if phone_by_user_id is not None:
        return True, phone_by_user_id.get(uid)
    prof = Profile.objects.filter(user_id=uid).only("phone").first()
    if prof and prof.phone:
        disp = format_phone_display(prof.phone) or prof.phone
        return True, disp or None
    return True, None


class VoucherClaimView(APIView):
    """
    POST /api/voucher/vouchers/claim
    Link an unlinked ParkPe gift voucher to the logged-in user (voucherCode + PIN).
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        code_raw = (body.get("voucherCode") or body.get("voucher_code") or "").strip()
        pin_raw = body.get("pin")
        pin = str(pin_raw).strip() if pin_raw is not None else ""
        if not code_raw or not pin:
            return Response(
                {"detail": "voucherCode and pin are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        brand_id = get_parkpe_brand_id()
        if not brand_id:
            return Response(
                {"detail": "Voucher service not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        code = unformat_voucher_code(code_raw)
        if len(code) != 16:
            return Response(
                {"detail": "Invalid voucher code format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            v = GiftVoucher.objects.get(voucher_code=code, brand_id=brand_id)
        except GiftVoucher.DoesNotExist:
            log_parkpe(
                "parkpe_voucher",
                "Claim voucher not found",
                False,
                request,
                {"code_masked": _mask_voucher_code(code)},
            )
            return Response({"detail": "Voucher not found."}, status=status.HTTP_404_NOT_FOUND)

        meta_pre = v.metadata or {}
        stored = meta_pre.get("parkpe_user_id")
        if stored is not None:
            try:
                if int(stored) == request.user.pk:
                    log_parkpe(
                        "parkpe_voucher",
                        "Claim voucher already linked same user",
                        True,
                        request,
                        {"voucher_id": v.id},
                    )
                    return Response(
                        {
                            "success": True,
                            "message": "Voucher already linked to your account.",
                            "voucherId": v.id,
                        }
                    )
            except (TypeError, ValueError):
                pass
            log_parkpe(
                "parkpe_voucher",
                "Claim voucher already linked other user",
                False,
                request,
                {"voucher_id": v.id},
            )
            return Response(
                {"detail": "This voucher is already linked to another account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        voucher_service = VoucherService()
        is_valid, err = voucher_service.verify_pin(v, pin, increment_retry=True)
        if not is_valid:
            log_parkpe(
                "parkpe_voucher",
                "Claim voucher PIN failed",
                False,
                request,
                {"voucher_id": v.id},
            )
            return Response(
                {"detail": err or "Invalid PIN."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        v.refresh_from_db()

        with transaction.atomic():
            locked = GiftVoucher.objects.select_for_update().get(pk=v.pk)
            m = dict(locked.metadata or {})
            existing = m.get("parkpe_user_id")
            if existing is not None:
                try:
                    ex_uid = int(existing)
                except (TypeError, ValueError):
                    return Response(
                        {"detail": "This voucher is already linked to another account."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if ex_uid != request.user.pk:
                    return Response(
                        {"detail": "This voucher is already linked to another account."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                log_parkpe(
                    "parkpe_voucher",
                    "Claim voucher race already linked",
                    True,
                    request,
                    {"voucher_id": locked.id},
                )
                return Response(
                    {
                        "success": True,
                        "message": "Voucher already linked to your account.",
                        "voucherId": locked.id,
                    }
                )

            m["parkpe_user_id"] = request.user.pk
            locked.metadata = m
            locked.save(update_fields=["metadata"])

        log_parkpe(
            "parkpe_voucher",
            "Claim voucher success",
            True,
            request,
            {"voucher_id": v.id},
        )
        return Response(
            {
                "success": True,
                "message": "Voucher linked to your account.",
                "voucherId": v.id,
            }
        )


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
        uid_list = []
        for v in vouchers:
            raw = (v.metadata or {}).get("parkpe_user_id")
            if raw is not None:
                uid_list.append(raw)
        phone_map = _phone_display_map_for_user_ids(uid_list)
        items = []
        for v in vouchers:
            plinked, lphone = _parkpe_linked_fields(v.metadata, phone_map)
            items.append(
                {
                    "id": v.id,
                    "voucherCodeMasked": _mask_voucher_code(v.voucher_code),
                    "referenceNumber": v.reference_number,
                    "originalAmount": float(v.original_amount),
                    "currentBalance": float(v.current_balance),
                    "currency": v.currency or "INR",
                    "status": v.status,
                    "issuedAt": v.issued_at.isoformat() if v.issued_at else None,
                    "parkpeLinked": plinked,
                    "linkedUserPhone": lphone,
                }
            )
        log_parkpe("parkpe_voucher", "Voucher list", True, request, {"total": total})
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
            log_parkpe("parkpe_voucher", "Voucher detail not found", False, request, {"voucher_id": voucher_id})
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
                "transactionType": (
                    "REFUND"
                    if (
                        ("ROLLBACK" in str(t.transaction_type).upper())
                        or (str(t.transaction_type).upper() == "REFUND")
                        or ("-RB-" in str(t.transaction_ref or "").upper())
                        or ("ROLLBACK" in str((t.metadata or {}).get("type", "")).upper())
                    )
                    else t.transaction_type
                ),
                # Keep transaction id in original reference format only.
                "transactionId": t.transaction_ref or None,
                "transactionAmount": float(t.transaction_amount) if t.transaction_amount is not None else None,
                "balanceBefore": float(t.balance_before),
                "balanceAfter": float(t.balance_after),
                # Direction used by ParkPe UI badges (credit/debit)
                "transactionDirection": (
                    "credit"
                    if (
                        (str(t.transaction_type).upper() in ("ISSUANCE", "REFUND", "CREDIT"))
                        or ("ROLLBACK" in str(t.transaction_type).upper())
                        or ("-RB-" in str(t.transaction_ref or "").upper())
                        or ("ROLLBACK" in str((t.metadata or {}).get("type", "")).upper())
                        or (t.transaction_amount or 0) < 0
                    )
                    else "debit"
                ),
                "redemptionMethod": t.redemption_method,
                "transactionStatus": t.transaction_status,
                "transactionRef": t.transaction_ref,
                "createdAt": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txns
        ]
        plinked, lphone = _parkpe_linked_fields(v.metadata)
        log_parkpe("parkpe_voucher", "Voucher detail", True, request, {"voucher_id": voucher_id})
        return Response({
            "id": v.id,
            "voucherCode": code,
            "referenceNumber": v.reference_number,
            "originalAmount": float(v.original_amount),
            "currentBalance": float(v.current_balance),
            "currency": v.currency or "INR",
            "status": v.status,
            "issuedAt": v.issued_at.isoformat() if v.issued_at else None,
            "parkpeLinked": plinked,
            "linkedUserPhone": lphone,
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
            log_parkpe("parkpe_voucher", "Reveal PIN not found", False, request, {"voucher_id": voucher_id})
            return Response({"detail": "Voucher not found."}, status=status.HTTP_404_NOT_FOUND)
        if not v.metadata or "encrypted_pin" not in v.metadata:
            log_parkpe("parkpe_voucher", "Reveal PIN unavailable", False, request, {"voucher_id": voucher_id})
            return Response({"detail": "PIN not available for this voucher."}, status=status.HTTP_404_NOT_FOUND)
        try:
            pin = decrypt_data(v.metadata["encrypted_pin"])
        except Exception as e:
            logger.warning("parkpe_voucher_reveal_pin_failed", extra_data={"voucher_id": v.id, "error": str(e)})
            log_parkpe("parkpe_voucher", "Reveal PIN failed", False, request, {"voucher_id": voucher_id})
            return Response({"detail": "Could not retrieve PIN."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        log_parkpe("parkpe_voucher", "Reveal PIN", True, request, {"voucher_id": voucher_id})
        return Response({"pin": pin})
