"""
Parkpe BBPS API – for Angular frontend.
Uses Mobikwik backend (BBPSService). Request/response shapes match Angular bbps.model.
Send X-App: parkpe so product toggle (mobikwik_bbps) is checked for Parkpe.
"""
import uuid
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from api.mixins.response_mixin import StandardResponseMixin
from api_management.product_control import is_product_enabled
from portal.services.bbps_service import BBPSService
from portal.services.bbps_operators_loader import load_bbps_operators_from_db, load_bbps_operators_from_excel
from portal.utils.logging_helper import get_logger

logger = get_logger(__name__)


def _resolve_operator_id_for_mobikwik(operator_id: str):
    """Resolve frontend operator_id (biller_id) to Mobikwik 'op' when available."""
    if not operator_id or not operator_id.strip():
        return operator_id
    try:
        from portal.models import BBPSOperator
        rec = BBPSOperator.objects.filter(biller_id=operator_id.strip()).first()
        if rec and getattr(rec, "op", None) and str(rec.op).strip():
            return str(rec.op).strip()
    except Exception:
        pass
    return operator_id


def _get_operator_display_name(operator_id: str) -> str:
    """Get operator/biller display name for bill response."""
    if not operator_id or not operator_id.strip():
        return ""
    try:
        from portal.models import BBPSOperator
        rec = BBPSOperator.objects.filter(biller_id=operator_id.strip()).first()
        if rec and getattr(rec, "name", None):
            return str(rec.name).strip()
    except Exception:
        pass
    return operator_id or "Biller"


# Fallback operators when Mobikwik UAT returns 0 and Excel is missing (for Electricity)
PARKPE_BBPS_FALLBACK_OPERATORS = {
    "ELECTRICITY": [
        {"id": "bescom", "operatorId": "bescom", "code": "BESCOM", "name": "BESCOM", "parameters": [{"name": "consumerId", "label": "Consumer ID", "type": "text", "required": True, "maxLength": 20}]},
        {"id": "tata_power", "operatorId": "tata_power", "code": "TATA_POWER", "name": "TATA Power", "parameters": [{"name": "consumerId", "label": "Consumer ID", "type": "text", "required": True, "maxLength": 20}]},
    ],
}

# Categories matching Angular environment.bbps.categories (lowercase for frontend)
PARKPE_BBPS_CATEGORIES = [
    "electricity",
    "water",
    "gas",
    "dth",
    "broadband",
    "mobile_postpaid",
    "landline",
    "insurance",
    "loan_repayment",
    "municipal_taxes",
    "education",
    "subscription",
]


def _map_operator_to_angular(op: dict, category: str) -> dict:
    """Map backend operator dict to Angular BBPSOperator shape."""
    return {
        "id": str(op.get("id") or op.get("operatorId") or op.get("code") or ""),
        "name": op.get("name") or op.get("operatorName") or op.get("billerName") or "Operator",
        "code": op.get("code") or op.get("operatorCode") or op.get("id") or "",
        "category": category.lower() if category else "electricity",
        "logo": op.get("logo"),
        "description": op.get("description"),
        "parameters": op.get("parameters") or [
            {"name": "consumerId", "label": "Consumer ID", "type": "text", "required": True, "maxLength": 20},
        ],
        "paymentModes": op.get("paymentModes") or ["card", "netbanking", "upi"],
        "minAmount": op.get("minAmount"),
        "maxAmount": op.get("maxAmount"),
    }


class BBPSCategoriesView(APIView):
    """GET /api/bbps/categories – list categories for Parkpe (Angular)."""
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def get(self, request):
        if not is_product_enabled(None, "mobikwik_bbps", request):
            logger.warning("parkpe_bbps_categories disabled")
            return Response(
                {"detail": "BBPS (Mobikwik) is disabled for this app."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        logger.info("parkpe_bbps_categories", extra_data={"count": len(PARKPE_BBPS_CATEGORIES)})
        return Response(PARKPE_BBPS_CATEGORIES)


class BBPSOperatorsView(APIView):
    """GET /api/bbps/operators?category=electricity – list operators from Mobikwik (Angular shape)."""
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def get(self, request):
        if not is_product_enabled(None, "mobikwik_bbps", request):
            logger.warning("parkpe_bbps_operators disabled")
            return Response(
                {"detail": "BBPS (Mobikwik) is disabled for this app."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        category = (request.GET.get("category") or "electricity").strip()
        category_param = category.upper().replace(" ", "_") if category else None
        # Operators from DB first (Bharat Bill – Mobikwik/Euronet); then Excel fallback, then static
        db_ops = load_bbps_operators_from_db(bbps_enabled_only=True, category=category_param)
        if not db_ops:
            db_ops = load_bbps_operators_from_excel(bbps_enabled_only=True, category=category_param)
        if db_ops:
            operators = [
                {
                    "id": str(op.get("operator_id", "")),
                    "operatorId": op.get("operator_id"),
                    "code": op.get("operator_id"),
                    "name": op.get("name") or "Operator",
                    "parameters": [
                        {
                            "name": "consumerId",
                            "label": op.get("customer_label") or "Consumer ID",
                            "type": "text",
                            "required": True,
                            "maxLength": 20,
                        }
                    ],
                }
                for op in db_ops
            ]
        else:
            operators = PARKPE_BBPS_FALLBACK_OPERATORS.get(category_param) or []
        mapped = [_map_operator_to_angular(op, category) for op in operators]
        logger.info("parkpe_bbps_operators", extra_data={"category": category, "count": len(mapped)})
        return Response(mapped)


class BBPSFetchBillView(APIView):
    """POST /api/bbps/fetch-bill – body: operatorId, operatorCode, parameters (Angular BillFetchRequest)."""
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        if not is_product_enabled(None, "mobikwik_bbps", request):
            logger.warning("parkpe_bbps_fetch_bill disabled")
            return Response(
                {"detail": "BBPS (Mobikwik) is disabled for this app."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        body = request.data or {}
        operator_id = str(body.get("operatorId") or body.get("operatorCode") or "")
        parameters = body.get("parameters") or {}
        customer_id = str(
            parameters.get("consumerId")
            or parameters.get("customer_id")
            or parameters.get("connectionId")
            or parameters.get("consumer_id")
            or ""
        ).strip()
        if not operator_id or not customer_id:
            logger.warning("parkpe_bbps_fetch_bill missing params", extra_data={"operator_id": operator_id})
            return Response(
                {"detail": "operatorId/operatorCode and parameters.consumerId/customer_id required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.info("parkpe_bbps_fetch_bill", extra_data={"operator_id": operator_id})
        subscriber_id = (parameters.get("subscriber_id") or parameters.get("subscriberId") or "").strip() or None
        extra = {}
        for k in ("ad1", "ad2", "ad3", "ad4", "ad9"):
            v = parameters.get(k)
            if v not in (None, ""):
                extra[k] = str(v).strip()
        service = BBPSService(vendor="mobikwik")
        if not service.is_available():
            return Response(
                {"detail": "BBPS service is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        operator_id_for_api = _resolve_operator_id_for_mobikwik(operator_id)
        result = service.fetch_bill(
            operator_id=operator_id_for_api,
            customer_id=customer_id,
            subscriber_id=subscriber_id,
            extra=extra if extra else None,
        )
        if not result.get("success"):
            logger.warning(
                "parkpe_bbps_fetch_bill failed",
                extra_data={"operator_id": operator_id, "message": result.get("message")},
            )
            return Response(
                {"detail": result.get("message", "Bill fetch failed")},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        logger.info("parkpe_bbps_fetch_bill success", extra_data={"operator_id": operator_id})
        bill_details = result.get("bill_details") or {}
        if isinstance(bill_details, dict):
            amount_val = bill_details.get("amount") or bill_details.get("dueAmount") or bill_details.get("outstanding") or 0
            try:
                amount_val = float(amount_val)
            except (TypeError, ValueError):
                amount_val = 0
            bill_number = str(bill_details.get("billNumber") or bill_details.get("bill_number") or "")
            due_date = bill_details.get("dueDate") or bill_details.get("due_date") or ""
            bill_date = bill_details.get("billDate") or bill_details.get("bill_date") or ""
            details_list = [
                {"label": k.replace("_", " ").title(), "value": v}
                for k, v in bill_details.items()
                if k not in ("amount", "dueAmount", "outstanding") and v not in (None, "")
            ]
        else:
            amount_val = 0
            bill_number = ""
            due_date = ""
            bill_date = ""
            details_list = []
        ref_id = str(uuid.uuid4())[:16]
        operator_name = _get_operator_display_name(operator_id)
        angular_response = {
            "billId": ref_id,
            "operatorId": operator_id,
            "operatorName": operator_name,
            "consumerId": customer_id,
            "consumerName": None,
            "billNumber": bill_number,
            "billDate": bill_date,
            "dueDate": due_date,
            "amount": amount_val,
            "currency": "INR",
            "billDetails": details_list,
            "latePaymentCharge": None,
            "additionalInfo": None,
        }
        return Response(angular_response)


class BBPSPayBillView(APIView):
    """POST /api/bbps/pay – body: paymentMethod ('voucher'|'pg'), billId, operatorId, consumerId, amount, ... For pg: orderId, paymentId, gateway."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        if not is_product_enabled(None, "mobikwik_bbps", request):
            logger.warning("parkpe_bbps_pay disabled")
            return Response(
                {"detail": "BBPS (Mobikwik) is disabled for this app."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        body = request.data or {}
        payment_method = (body.get("paymentMethod") or body.get("payment_method") or "").strip().lower()
        if payment_method not in ("voucher", "pg"):
            return Response(
                {"detail": "paymentMethod is required and must be 'voucher' or 'pg'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        operator_id = str(body.get("operatorId") or "")
        consumer_id = str(body.get("consumerId") or "")
        amount = body.get("amount")
        bill_id = str(body.get("billId") or uuid.uuid4().hex[:16])
        if not operator_id or not consumer_id or amount is None:
            return Response(
                {"detail": "operatorId, consumerId and amount are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            amount_float = float(amount)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        ref_id = bill_id
        user = request.user

        # Check BBPS service config (voucher / pg allowed)
        try:
            from portal.models import ParkPeServiceConfig
            svc = ParkPeServiceConfig.objects.filter(service_code="BBPS", is_active=True).first()
            if svc:
                if payment_method == "voucher" and not svc.voucher_allowed:
                    return Response(
                        {"detail": "Voucher payment is not allowed for BBPS."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if payment_method == "pg" and not svc.pg_allowed:
                    return Response(
                        {"detail": "PG payment is not allowed for BBPS."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        except Exception:
            pass

        if payment_method == "voucher":
            try:
                from portal.services.parkpe_voucherx_bridge import debit_voucher_balance, get_balance
                debit_voucher_balance(
                    user,
                    amount_float,
                    reference_id=ref_id,
                    service_code="BBPS",
                    description=f"BBPS pay {operator_id}",
                )
            except ValueError as e:
                if "Insufficient" in str(e):
                    return Response(
                        {"detail": "Insufficient voucher balance."},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                raise
        else:
            # pg: verify PG payment (orderId, paymentId, gateway)
            order_id = body.get("orderId") or body.get("order_id")
            payment_id = body.get("paymentId") or body.get("payment_id")
            gateway = (body.get("gateway") or "").strip().lower()
            if not order_id or not payment_id or not gateway:
                return Response(
                    {"detail": "For paymentMethod 'pg', orderId, paymentId and gateway are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            verified = False
            if gateway == "cashfree":
                try:
                    from portal.services.vendors.cashfree_pg import CashfreePGClient
                    client = CashfreePGClient()
                    order_data = client.get_order(order_id)
                    order_status = (order_data.get("order_status") or order_data.get("orderStatus") or "").upper()
                    if order_status == "PAID":
                        verified = True
                    else:
                        payments = client.get_payment(order_id)
                        if isinstance(payments, list):
                            for p in payments:
                                if (p.get("payment_status") or p.get("paymentStatus") or "").upper() == "SUCCESS":
                                    verified = True
                                    break
                        elif isinstance(payments, dict) and (payments.get("payment_status") or payments.get("paymentStatus") or "").upper() == "SUCCESS":
                            verified = True
                except Exception as e:
                    logger.warning("parkpe_bbps_pay pg_verify_cashfree_error", extra_data={"order_id": order_id, "error": str(e)})
                    return Response(
                        {"detail": f"Payment verification failed: {str(e)}"},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
            else:
                return Response({"detail": "Only Cashfree PG is supported. Use gateway cashfree."}, status=status.HTTP_400_BAD_REQUEST)
            if not verified:
                return Response(
                    {"detail": "Payment not confirmed."},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        service = BBPSService(vendor="mobikwik")
        if not service.is_available():
            if payment_method == "voucher":
                try:
                    from portal.services.parkpe_voucherx_bridge import credit_voucher_balance
                    credit_voucher_balance(user, amount_float, reference_id=ref_id, service_code="BBPS", description="BBPS rollback")
                except Exception:
                    pass
            return Response(
                {"detail": "BBPS service is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        operator_id_for_api = _resolve_operator_id_for_mobikwik(operator_id)
        result = service.pay_bill(
            operator_id=operator_id_for_api,
            customer_id=consumer_id,
            amount=str(amount_float),
            ref_id=ref_id,
            subscriber_id=None,
            extra=None,
        )
        if not result.get("success"):
            if payment_method == "voucher":
                try:
                    from portal.services.parkpe_voucherx_bridge import credit_voucher_balance
                    credit_voucher_balance(user, amount_float, reference_id=ref_id, service_code="BBPS", description="BBPS rollback")
                except Exception:
                    pass
            logger.warning(
                "parkpe_bbps_pay failed",
                extra_data={"operator_id": operator_id, "message": result.get("message")},
            )
            return Response(
                {"detail": result.get("message", "Payment failed")},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        txn_id = result.get("transaction_id") or ref_id
        logger.info(
            "parkpe_bbps_pay success",
            extra_data={"operator_id": operator_id, "transaction_id": txn_id, "payment_method": payment_method},
        )
        status_val = result.get("status") or "SUBMITTED"
        angular_response = {
            "success": True,
            "transactionId": txn_id,
            "billId": bill_id,
            "receiptNumber": txn_id,
            "amount": amount_float,
            "status": status_val,
            "timestamp": None,
            "message": "Payment submitted",
        }
        return Response(angular_response)
