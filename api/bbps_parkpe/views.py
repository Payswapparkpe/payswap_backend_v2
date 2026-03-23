"""
Parkpe BBPS API – for Angular frontend.
Uses Mobikwik backend (BBPSService). Request/response shapes match Angular bbps.model.
Send X-App: parkpe so product toggle (mobikwik_bbps) is checked for Parkpe.
"""
from collections.abc import Mapping

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from api.mixins.response_mixin import StandardResponseMixin
from portal.services.bbps_service import BBPSService
from portal.services.bbps_operators_loader import (
    get_bbps_categories,
    load_bbps_operators_from_db,
    load_bbps_operators_from_excel,
)
from portal.utils.logging_helper import get_logger

from api.parkpe_logging import log_parkpe
from portal.utils.transaction_id import generate_transaction_id

logger = get_logger(__name__)
MOBIKWIK_OPERATOR_ICON_BASE = "https://static.mobikwik.com/appdata/operator_icons"


def _cashfree_payments_normalize(payments_raw):
    """Cashfree PGOrderFetchPayments may return a dict with nested list or a single payment dict."""
    if payments_raw is None:
        return []
    if isinstance(payments_raw, list):
        return payments_raw
    if isinstance(payments_raw, dict):
        st = (payments_raw.get("payment_status") or payments_raw.get("paymentStatus") or "").upper()
        if st == "SUCCESS":
            return [payments_raw]
        for key in ("payments", "payment_details", "data", "docs"):
            inner = payments_raw.get(key)
            if isinstance(inner, list):
                return inner
    return []


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


def _resolve_mobikwik_op_id(operator_id: str) -> str | None:
    """Resolve saved/favorite operatorId (biller_id) to Mobikwik op id."""
    operator_id = str(operator_id or "").strip()
    if not operator_id:
        return None
    try:
        from portal.models import BBPSOperator
        rec = BBPSOperator.objects.filter(biller_id=operator_id).only("op").first()
        if rec and getattr(rec, "op", None):
            op_val = str(rec.op).strip()
            if op_val.endswith(".0") and op_val[:-2].isdigit():
                op_val = op_val[:-2]
            if op_val:
                return op_val
    except Exception:
        pass
    return None


def _mobikwik_operator_icon_url(*candidates) -> str | None:
    """Build Mobikwik icon URL from op/operator ids."""
    for raw in candidates:
        value = str(raw or "").strip()
        if not value:
            continue
        # Handle numeric-like values from sheets/DB (e.g. "62.0")
        if value.endswith(".0") and value[:-2].isdigit():
            value = value[:-2]
        lower = value.lower()
        if lower.startswith("op") and value[2:].isdigit():
            return f"{MOBIKWIK_OPERATOR_ICON_BASE}/{lower}.png"
        if value.isdigit():
            return f"{MOBIKWIK_OPERATOR_ICON_BASE}/op{value}.png"
    return None


def _log_context_from_request(request, api_name: str):
    """Build log_context so Mobikwik API call is logged and linked to this Parkpe request (dono log ka diff)."""
    return {
        "request_id": getattr(request, "request_id", None),
        "response_id": getattr(request, "response_id", None),
        "source": "ParkPe",
        "api_name": api_name,
    }


def _vendor_response_id_from_result(result, action: str):
    """Extract vendor API response/transaction ID from BBPSService result for logging."""
    if not result or not isinstance(result, dict):
        return None
    data = result.get("data") or {}
    if action == "pay_bill":
        return result.get("transaction_id") or data.get("transactionId") or data.get("refId") or data.get("transaction_id") or data.get("ref_id")
    if action == "payment_status":
        return data.get("transactionId") or data.get("refId") or result.get("ref_id")
    if action == "fetch_bill":
        bill_details = result.get("bill_details") or data.get("billDetails") or data.get("bill_details") or data
        if isinstance(bill_details, dict):
            return bill_details.get("billId") or bill_details.get("bill_id") or data.get("refId") or data.get("referenceId")
    return data.get("responseId") or data.get("refId") or data.get("transactionId") or data.get("transaction_id")


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
    mobikwik_op_id = str(op.get("op") or "").strip() or None
    # Strict Mobikwik icon mapping: always use op id URL when available.
    logo = _mobikwik_operator_icon_url(mobikwik_op_id) or op.get("logo") or op.get("icon") or op.get("icon_url")
    return {
        "id": str(op.get("id") or op.get("operatorId") or op.get("code") or ""),
        "name": op.get("name") or op.get("operatorName") or op.get("billerName") or "Operator",
        "code": op.get("code") or op.get("operatorCode") or op.get("id") or "",
        "mobikwikOpId": mobikwik_op_id,
        "category": category.lower() if category else "electricity",
        "logo": logo,
        "description": op.get("description"),
        "parameters": op.get("parameters") or [
            {"name": "consumerId", "label": "Consumer ID", "type": "text", "required": True, "maxLength": 20},
        ],
        "paymentModes": op.get("paymentModes") or ["card", "netbanking", "upi"],
        "minAmount": op.get("minAmount"),
        "maxAmount": op.get("maxAmount"),
    }


class BBPSCategoriesView(APIView):
    """GET /api/bbps/categories – list categories for Parkpe (Angular). Requires auth."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        raw = get_bbps_categories()
        normalized = [c.strip().lower().replace(" ", "_") for c in raw if c and str(c).strip()]
        # Deduplicate so UI shows each category once (e.g. MORE section)
        categories = sorted(set(normalized)) if normalized else []
        if not categories:
            categories = PARKPE_BBPS_CATEGORIES
        logger.info("parkpe_bbps_categories", extra_data={"count": len(categories)})
        log_parkpe(
            "parkpe_bbps", "Categories", True, request,
            extra_data={"count": len(categories)},
            request_method="GET",
            request_body=dict(request.GET) if request.GET else {},
            response_status=status.HTTP_200_OK,
            response_body=categories,
        )
        return Response(categories)


class BBPSOperatorsView(APIView):
    """GET /api/bbps/operators?category=electricity – list operators from Mobikwik (Angular shape). Requires auth."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        category = (request.GET.get("category") or "electricity").strip()
        category_param = category.upper().replace(" ", "_") if category else None
        is_fastag = bool(category_param and "FASTAG" in category_param)
        # Operators from DB first (Bharat Bill – Mobikwik/Euronet); then Excel fallback, then static
        db_ops = load_bbps_operators_from_db(bbps_enabled_only=True, category=category_param)
        if not db_ops and is_fastag:
            try:
                from django.db.models import Q
                from portal.models import BBPSOperator

                qs = (
                    BBPSOperator.objects.filter(is_active=True)
                    .filter(
                        Q(category__icontains="FASTAG")
                        | Q(name__icontains="FASTAG")
                    )
                    .order_by("name")
                )
                db_ops = [
                    {
                        "operator_id": str(op.biller_id or op.op or "").strip(),
                        "name": op.name or "Operator",
                        "customer_label": op.customer_label or "Vehicle Number",
                    }
                    for op in qs
                    if str(op.biller_id or op.op or "").strip()
                ]
            except Exception:
                db_ops = []
        if not db_ops:
            db_ops = load_bbps_operators_from_excel(bbps_enabled_only=True, category=category_param)
        # FASTag fallback: if strict category match fails, scan all operators and pick FASTag-like rows.
        if not db_ops and is_fastag:
            try:
                all_ops = load_bbps_operators_from_excel(bbps_enabled_only=True, category=None) or []
                filtered = []
                for op in all_ops:
                    cat_text = str(op.get("category") or "").upper()
                    name_text = str(op.get("name") or "").upper()
                    if "FASTAG" not in cat_text and "FASTAG" not in name_text:
                        continue
                    op_id = str(op.get("operator_id") or op.get("biller_id") or op.get("op") or "").strip()
                    if not op_id:
                        continue
                    filtered.append({
                        "operator_id": op_id,
                        "name": op.get("name") or "FASTag Operator",
                        "customer_label": op.get("customer_label") or "Vehicle Number",
                    })
                db_ops = filtered
            except Exception:
                db_ops = []
        if db_ops:
            def _build_parameters(op):
                params = [
                    {
                        "name": "consumerId",
                        "label": op.get("customer_label") or "Consumer ID",
                        "type": "text",
                        "required": True,
                        "maxLength": 20,
                    }
                ]
                for i, key in enumerate(("ad1", "ad2", "ad3", "ad4", "ad9"), 1):
                    params.append({
                        "name": key,
                        "label": f"Additional {i}",
                        "type": "text",
                        "required": False,
                    })
                return params

            operators = [
                {
                    "id": str(op.get("operator_id", "")),
                    "operatorId": op.get("operator_id"),
                    "code": op.get("operator_id"),
                    "op": op.get("op"),
                    "name": op.get("name") or "Operator",
                    "parameters": _build_parameters(op),
                }
                for op in db_ops
            ]
        else:
            operators = PARKPE_BBPS_FALLBACK_OPERATORS.get(category_param) or []
        mapped = [_map_operator_to_angular(op, category) for op in operators]
        logger.info("parkpe_bbps_operators", extra_data={"category": category, "count": len(mapped)})
        log_parkpe(
            "parkpe_bbps", "Operators", True, request,
            extra_data={"category": category, "count": len(mapped)},
            request_method="GET",
            request_body=dict(request.GET) if request.GET else {},
            response_status=status.HTTP_200_OK,
            response_body={"count": len(mapped), "operators_sample": mapped[:3] if len(mapped) > 3 else mapped},
        )
        return Response(mapped)


class BBPSFetchBillView(APIView):
    """POST /api/bbps/fetch-bill – body: operatorId, operatorCode, parameters (Angular BillFetchRequest). Requires auth."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        body = getattr(request, "data", None) or {}
        log_parkpe(
            "parkpe_bbps", "Fetch bill request", True, request,
            extra_data={},
            request_method="POST",
            request_body=body,
        )
        try:
            return self._fetch_bill_impl(request)
        except Exception:
            logger.exception("parkpe_bbps_fetch_bill unhandled error")
            resp = {"detail": "Bill fetch failed. Please try again."}
            log_parkpe(
                "parkpe_bbps", "Fetch bill error", False, request,
                extra_data={"message": "Unhandled error"},
                request_method="POST",
                request_body=body,
                response_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                response_body=resp,
            )
            return Response(resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _fetch_bill_impl(self, request):
        raw = getattr(request, "data", None) or {}
        body = raw if isinstance(raw, dict) else {}
        operator_id = str(body.get("operatorId") or body.get("operatorCode") or "")
        _params = body.get("parameters")
        parameters = _params if isinstance(_params, dict) else {}
        customer_id = str(
            parameters.get("consumerId")
            or parameters.get("customer_id")
            or parameters.get("connectionId")
            or parameters.get("consumer_id")
            or ""
        ).strip()
        if not operator_id or not customer_id:
            logger.warning("parkpe_bbps_fetch_bill missing params", extra_data={"operator_id": operator_id})
            resp = {"detail": "operatorId/operatorCode and parameters.consumerId/customer_id required."}
            log_parkpe("parkpe_bbps", "Fetch bill missing params", False, request, extra_data={"operator_id": operator_id}, request_method="POST", request_body=body, response_status=status.HTTP_400_BAD_REQUEST, response_body=resp)
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)
        logger.info("parkpe_bbps_fetch_bill", extra_data={"operator_id": operator_id})
        subscriber_id = (parameters.get("subscriber_id") or parameters.get("subscriberId") or "").strip() or None
        extra = {}
        # adParams: ad1, ad2, ad3, ad4, ad9
        for k in ("ad1", "ad2", "ad3", "ad4", "ad9"):
            v = parameters.get(k)
            if v not in (None, ""):
                extra[k] = str(v).strip()
        # cir (circle): per Mobikwik API doc – from parameters first, else BBPSOperator
        if "cir" not in extra and "circle" not in extra:
            cir_val = parameters.get("cir") or parameters.get("circle")
            if cir_val not in (None, ""):
                extra["cir"] = str(cir_val).strip()
        if "cir" not in extra:
            try:
                from portal.models import BBPSOperator
                op_record = BBPSOperator.objects.filter(biller_id=operator_id.strip(), is_active=True).first()
                if op_record and getattr(op_record, "circle", None) and str(op_record.circle).strip():
                    extra["cir"] = str(op_record.circle).strip()
            except Exception:
                pass
        service = BBPSService(vendor="mobikwik")
        if not service.is_available():
            resp = {"detail": "BBPS service is not configured."}
            log_parkpe("parkpe_bbps", "Fetch bill service unavailable", False, request, extra_data={"vendor_called": False}, request_method="POST", request_body=body, response_status=status.HTTP_503_SERVICE_UNAVAILABLE, response_body=resp)
            return Response(resp, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        operator_id_for_api = _resolve_operator_id_for_mobikwik(operator_id)
        resolved_str = (operator_id_for_api or "").strip() if operator_id_for_api is not None else ""
        if not resolved_str:
            resp = {"detail": "This biller is not configured for bill fetch (missing operator id)."}
            log_parkpe("parkpe_bbps", "Fetch bill biller not configured", False, request, extra_data={"operator_id": operator_id, "vendor_called": False}, request_method="POST", request_body=body, response_status=status.HTTP_400_BAD_REQUEST, response_body=resp)
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)
        if not resolved_str.isdigit():
            resp = {"detail": "This biller is not configured for bill fetch (missing operator id)."}
            log_parkpe("parkpe_bbps", "Fetch bill invalid operator id", False, request, extra_data={"operator_id": operator_id, "vendor_called": False}, request_method="POST", request_body=body, response_status=status.HTTP_400_BAD_REQUEST, response_body=resp)
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = service.fetch_bill(
                operator_id=operator_id_for_api,
                customer_id=customer_id,
                subscriber_id=subscriber_id,
                extra=extra if extra else None,
                log_context=_log_context_from_request(request, "Fetch Bill"),
            )
        except Exception:
            logger.exception("parkpe_bbps_fetch_bill service error", extra_data={"operator_id": operator_id})
            resp = {"detail": "Bill fetch failed. Please try again."}
            log_parkpe(
                "parkpe_bbps", "Fetch bill service error", False, request,
                extra_data={"operator_id": operator_id, "vendor_called": True},
                request_method="POST",
                request_body=body,
                response_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                response_body=resp,
            )
            return Response(resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not result.get("success"):
            msg = result.get("message", "Bill fetch failed")
            logger.warning(
                "parkpe_bbps_fetch_bill failed: " + (msg or "Bill fetch failed"),
                user=getattr(request, "user", None),
                request_id=getattr(request, "request_id", None),
                url=request.path if request else None,
                extra_data={"operator_id": operator_id, "message": msg, "vendor_called": True},
            )
            resp_fail = {"success": False, "detail": msg}
            vendor_resp_id = _vendor_response_id_from_result(result, "fetch_bill")
            extra_fail = {"operator_id": operator_id, "message": msg, "vendor_called": True}
            if vendor_resp_id:
                extra_fail["vendor_response_id"] = vendor_resp_id
            log_parkpe(
                "parkpe_bbps", "Fetch bill failed", False, request,
                extra_data=extra_fail,
                request_method="POST",
                request_body=body,
                response_status=status.HTTP_200_OK,
                response_body=resp_fail,
            )
            return Response(resp_fail, status=status.HTTP_200_OK)
        logger.info("parkpe_bbps_fetch_bill success", extra_data={"operator_id": operator_id})
        try:
            bill_details = result.get("bill_details") or {}
            if not isinstance(bill_details, dict):
                bill_details = {}
            # Mobikwik: billAmount, billnetamount; generic: amount, dueAmount, etc.
            amount_val = (
                bill_details.get("billAmount")
                or bill_details.get("billnetamount")
                or bill_details.get("amount")
                or bill_details.get("dueAmount")
                or bill_details.get("outstanding")
                or bill_details.get("due_amount")
                or bill_details.get("outstanding_amount")
                or bill_details.get("total_amount")
                or bill_details.get("minBillAmount")
                or 0
            )
            try:
                amount_val = float(amount_val)
            except (TypeError, ValueError):
                amount_val = 0
            bill_number = str(
                bill_details.get("billNumber")
                or bill_details.get("bill_number")
                or bill_details.get("bill_no")
                or ""
            )
            due_date = bill_details.get("dueDate") or bill_details.get("due_date") or ""
            bill_date = bill_details.get("billDate") or bill_details.get("bill_date") or bill_details.get("billdate") or ""
            consumer_name = (
                bill_details.get("consumerName")
                or bill_details.get("consumer_name")
                or bill_details.get("userName")
                or bill_details.get("user_name")
                or bill_details.get("customerName")
                or bill_details.get("customer_name")
                or ""
            )
            amount_keys = ("amount", "dueAmount", "outstanding", "due_amount", "outstanding_amount", "total_amount", "billAmount", "billnetamount", "minBillAmount")
            bill_no_keys = ("billNumber", "bill_number", "bill_no")
            skip_keys = ("Data", "data", "userName", "user_name", "consumerName", "consumer_name", "customerName", "customer_name", "acceptPartPay", "accept_part_pay", "minBillAmount", "min_bill_amount")
            details_list = []
            for k, v in bill_details.items():
                if k in amount_keys or k in bill_no_keys or k in skip_keys or v is None or v == "":
                    continue
                try:
                    val = v if isinstance(v, (str, int, float, bool)) else str(v)
                except Exception:
                    val = str(v) if v is not None else ""
                details_list.append({"label": k.replace("_", " ").title(), "value": val})
            accept_part_pay = bill_details.get("acceptPartPay") or bill_details.get("accept_part_pay")
            if isinstance(accept_part_pay, str):
                accept_part_pay = str(accept_part_pay).lower() in ("true", "1", "yes")
            min_bill = bill_details.get("minBillAmount") or bill_details.get("min_bill_amount")
            try:
                min_bill = float(min_bill) if min_bill is not None else None
            except (TypeError, ValueError):
                min_bill = None
            ref_id = generate_transaction_id()
            operator_name = _get_operator_display_name(operator_id)
            angular_response = {
                "billId": ref_id,
                "operatorId": operator_id,
                "operatorName": operator_name,
                "consumerId": customer_id,
                "consumerName": consumer_name or None,
                "billNumber": bill_number,
                "billDate": bill_date,
                "dueDate": due_date,
                "amount": amount_val,
                "currency": "INR",
                "billDetails": details_list,
                "latePaymentCharge": None,
                "additionalInfo": None,
                "acceptPartPay": bool(accept_part_pay),
                "minBillAmount": min_bill,
            }
            vendor_resp_id = _vendor_response_id_from_result(result, "fetch_bill")
            extra_ok = {"operator_id": operator_id, "vendor_called": True}
            if vendor_resp_id:
                extra_ok["vendor_response_id"] = vendor_resp_id
            log_parkpe(
                "parkpe_bbps", "Fetch bill success", True, request,
                extra_data=extra_ok,
                request_method="POST",
                request_body=body,
                response_status=status.HTTP_200_OK,
                response_body=angular_response,
            )
            return Response(angular_response)
        except Exception:
            logger.exception("parkpe_bbps_fetch_bill build response error", extra_data={"operator_id": operator_id})
            resp = {"detail": "Bill fetch failed. Please try again."}
            log_parkpe(
                "parkpe_bbps", "Fetch bill response build error", False, request,
                extra_data={"operator_id": operator_id, "message": "Failed to build bill response", "vendor_called": True},
                request_method="POST",
                request_body=body,
                response_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                response_body=resp,
            )
            return Response(resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BBPSPayBillView(APIView):
    """POST /api/bbps/pay – body: paymentMethod ('voucher'|'pg'), billId, operatorId, consumerId, amount, ... For pg: orderId, paymentId, gateway."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        body = request.data or {}
        if not isinstance(body, Mapping):
            return Response(
                {"detail": "Invalid request payload. Please send a JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payment_method = (body.get("paymentMethod") or body.get("payment_method") or "").strip().lower()
        if payment_method not in ("voucher", "pg"):
            return Response(
                {"detail": "paymentMethod is required and must be 'voucher' or 'pg'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        operator_id = str(body.get("operatorId") or "")
        consumer_id = str(body.get("consumerId") or "")
        amount = body.get("amount")
        bill_id = str(body.get("billId") or generate_transaction_id())
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

        voucher = None
        amount_decimal = None
        voucher_pin = None
        voucher_redeemed = False
        voucher_debit_ref = None
        if payment_method == "voucher":
            voucher_id = body.get("voucher_id")
            pin = body.get("pin")
            if voucher_id is None or not str(pin or "").strip():
                return Response(
                    {"detail": "Select a voucher and enter PIN to pay."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                voucher_id = int(voucher_id)
            except (TypeError, ValueError):
                return Response({"detail": "Invalid voucher selection."}, status=status.HTTP_400_BAD_REQUEST)
            from decimal import Decimal
            from portal.models import GiftVoucher
            from portal.services.parkpe_voucherx_bridge import get_parkpe_brand_id
            from portal.services.voucher_service import VoucherService

            brand_id = get_parkpe_brand_id()
            if not brand_id:
                return Response(
                    {"detail": "Voucher service not configured."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            voucher = (
                GiftVoucher.objects.filter(
                    id=voucher_id,
                    brand_id=brand_id,
                    metadata__parkpe_user_id=user.pk,
                    status__in=["ACTIVE", "PARTIALLY_REDEEMED"],
                    current_balance__gte=amount_float,
                )
                .first()
            )
            if not voucher:
                return Response(
                    {"detail": "Voucher not found or insufficient balance."},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
            amount_decimal = Decimal(str(amount_float))
            voucher_pin = str(pin).strip()
            # Pre-debit voucher fund first. If BBPS fails later, rollback to SAME voucher.
            voucher_service = VoucherService()
            try:
                is_pin_valid, pin_err = voucher_service.verify_pin(voucher, voucher_pin, increment_retry=True)
            except Exception as e:
                logger.exception(
                    "parkpe_bbps_pay voucher_pin_verify_error",
                    extra_data={"user_id": user.pk, "voucher_id": voucher.id, "ref_id": bill_id, "error": str(e)},
                )
                return Response(
                    {"detail": "Could not verify voucher PIN. Please try again."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not is_pin_valid:
                return Response({"detail": pin_err or "Invalid PIN."}, status=status.HTTP_400_BAD_REQUEST)
            if amount_decimal > voucher.current_balance:
                return Response(
                    {"detail": "Voucher not found or insufficient balance."},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
            from portal.models import ParkPeVoucherTransaction
            from django.db import transaction as db_transaction
            try:
                # GiftVoucherTransaction.transaction_ref is globally unique.
                # Retrying same billId after a rollback must use a new debit reference.
                voucher_debit_ref = generate_transaction_id()
                voucher_service.redeem_voucher_pin(
                    voucher_code=voucher.voucher_code,
                    pin=voucher_pin,
                    amount=amount_decimal,
                    transaction_ref=voucher_debit_ref,
                )
                voucher_redeemed = True
                with db_transaction.atomic():
                    ParkPeVoucherTransaction.objects.create(
                        user=user,
                        amount=amount_decimal,
                        transaction_type=ParkPeVoucherTransaction.DEBIT,
                        balance_after=None,
                        reference_id=ref_id,
                        service_code="BBPS",
                        description=bbps_pay_description,
                    )
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # pg: verify PG payment (orderId, gateway). paymentId optional — resolved from Cashfree if missing.
            order_id = body.get("orderId") or body.get("order_id")
            payment_id = body.get("paymentId") or body.get("payment_id")
            gateway = (body.get("gateway") or "").strip().lower()
            if not order_id or not gateway:
                return Response(
                    {"detail": "For paymentMethod 'pg', orderId and gateway are required."},
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
                    payments_raw = client.get_payment(order_id)
                    pay_list = _cashfree_payments_normalize(payments_raw)
                    if not verified:
                        for p in pay_list:
                            if (p.get("payment_status") or p.get("paymentStatus") or "").upper() == "SUCCESS":
                                verified = True
                                break
                    if verified and not (payment_id and str(payment_id).strip()):
                        for p in pay_list:
                            if (p.get("payment_status") or p.get("paymentStatus") or "").upper() == "SUCCESS":
                                payment_id = (
                                    p.get("cf_payment_id")
                                    or p.get("payment_id")
                                    or p.get("paymentId")
                                    or p.get("cfPaymentId")
                                )
                                break
                    if verified and not (payment_id and str(payment_id).strip()):
                        payment_id = order_id
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

        try:
            service = BBPSService(vendor="mobikwik")
            if not service.is_available():
                if payment_method == "voucher" and voucher_redeemed and voucher is not None and amount_decimal is not None:
                    try:
                        from django.db import transaction as db_transaction
                        from django.utils import timezone
                        from portal.models import GiftVoucher, GiftVoucherTransaction, ParkPeVoucherTransaction
                        with db_transaction.atomic():
                            v = GiftVoucher.objects.select_for_update().get(id=voucher.id)
                            before = v.current_balance
                            after = before + amount_decimal
                            v.current_balance = after
                            v.last_transaction_at = timezone.now()
                            if after == 0:
                                v.status = 'FULLY_REDEEMED'
                            elif after < v.original_amount:
                                v.status = 'PARTIALLY_REDEEMED'
                            else:
                                v.status = 'ACTIVE'
                            v.save(update_fields=["current_balance", "last_transaction_at", "status"])
                            GiftVoucherTransaction.objects.create(
                                voucher=v,
                                transaction_type='REDEMPTION',
                                transaction_amount=amount_decimal,
                                balance_before=before,
                                balance_after=after,
                                redemption_method='PIN',
                                transaction_status='SUCCESS',
                                transaction_ref=generate_transaction_id(),
                                metadata={
                                    "rollback_for": ref_id,
                                    "debit_ref": voucher_debit_ref,
                                    "reason": "service_unavailable",
                                    "type": "BBPS_ROLLBACK",
                                },
                            )
                            ParkPeVoucherTransaction.objects.create(
                                user=user,
                                amount=amount_decimal,
                                transaction_type=ParkPeVoucherTransaction.CREDIT,
                                balance_after=None,
                                reference_id=ref_id,
                                service_code="BBPS",
                                description=bbps_rollback_description,
                            )
                    except Exception:
                        logger.exception("parkpe_bbps_pay rollback_failed_service_unavailable", extra_data={"ref_id": ref_id})
                return Response(
                    {"detail": "BBPS service is not configured."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            operator_id_for_api = _resolve_operator_id_for_mobikwik(operator_id)
            customer_mobile = str(body.get("customerPhone") or body.get("customerMobile") or "").strip()
            payment_account_info = str(body.get("paymentAccountInfo") or "").strip()
            if not payment_account_info:
                # Mobikwik rejects empty paymentAccountInfo; fallback to customer mobile for voucher/UPI flow.
                payment_account_info = customer_mobile
            pay_extra = {
                "remitterName": str(body.get("customerName") or body.get("remitterName") or "").strip(),
                "customerMobile": customer_mobile,
                "paymentAccountInfo": payment_account_info,
                "paymentMode": str(body.get("paymentMode") or "UPI").strip() or "UPI",
                "paymentRefID": str(body.get("paymentRefID") or ref_id).strip() or ref_id,
            }
            # remove empty optional keys (Mobikwik rejects mandatory remitterName; keep that key as-is)
            pay_extra = {k: v for k, v in pay_extra.items() if v is not None and (v != "" or k == "remitterName")}
            result = service.pay_bill(
                operator_id=operator_id_for_api,
                customer_id=consumer_id,
                amount=str(amount_float),
                ref_id=ref_id,
                subscriber_id=None,
                extra=pay_extra,
                log_context=_log_context_from_request(request, "Pay Bill"),
            )
            if not result.get("success"):
                if payment_method == "voucher" and voucher_redeemed and voucher is not None and amount_decimal is not None:
                    try:
                        from django.db import transaction as db_transaction
                        from django.utils import timezone
                        from portal.models import GiftVoucher, GiftVoucherTransaction, ParkPeVoucherTransaction
                        with db_transaction.atomic():
                            v = GiftVoucher.objects.select_for_update().get(id=voucher.id)
                            before = v.current_balance
                            after = before + amount_decimal
                            v.current_balance = after
                            v.last_transaction_at = timezone.now()
                            if after == 0:
                                v.status = 'FULLY_REDEEMED'
                            elif after < v.original_amount:
                                v.status = 'PARTIALLY_REDEEMED'
                            else:
                                v.status = 'ACTIVE'
                            v.save(update_fields=["current_balance", "last_transaction_at", "status"])
                            GiftVoucherTransaction.objects.create(
                                voucher=v,
                                transaction_type='REDEMPTION',
                                transaction_amount=amount_decimal,
                                balance_before=before,
                                balance_after=after,
                                redemption_method='PIN',
                                transaction_status='SUCCESS',
                                transaction_ref=generate_transaction_id(),
                                metadata={
                                    "rollback_for": ref_id,
                                    "debit_ref": voucher_debit_ref,
                                    "reason": "vendor_failed",
                                    "type": "BBPS_ROLLBACK",
                                },
                            )
                            ParkPeVoucherTransaction.objects.create(
                                user=user,
                                amount=amount_decimal,
                                transaction_type=ParkPeVoucherTransaction.CREDIT,
                                balance_after=None,
                                reference_id=ref_id,
                                service_code="BBPS",
                                description=bbps_rollback_description,
                            )
                    except Exception:
                        logger.exception("parkpe_bbps_pay rollback_failed_vendor_failed", extra_data={"ref_id": ref_id})
                logger.warning(
                    "parkpe_bbps_pay failed",
                    extra_data={"operator_id": operator_id, "message": result.get("message")},
                )
                resp_fail = {"detail": result.get("message", "Payment failed")}
                vendor_resp_id = _vendor_response_id_from_result(result, "pay_bill")
                extra_fail = {"operator_id": operator_id, "message": result.get("message")}
                if vendor_resp_id:
                    extra_fail["vendor_response_id"] = vendor_resp_id
                log_parkpe(
                    "parkpe_bbps", "Pay bill failed", False, request,
                    extra_data=extra_fail,
                    request_method="POST",
                    request_body=body,
                    response_status=status.HTTP_502_BAD_GATEWAY,
                    response_body=resp_fail,
                )
                return Response(resp_fail, status=status.HTTP_502_BAD_GATEWAY)
            txn_id = result.get("transaction_id") or ref_id
            logger.info(
                "parkpe_bbps_pay success",
                extra_data={"operator_id": operator_id, "transaction_id": txn_id, "payment_method": payment_method},
            )
            try:
                from decimal import Decimal
                from portal.services.hub_income_service import record_hub_income
                from portal.models import ResellerPartner
                parkpe = ResellerPartner.objects.filter(partner_code='parkpe').first()
                record_hub_income(
                    'bbps',
                    transaction_amount=Decimal(str(amount_float)),
                    vendor_code=result.get('vendor') or 'mobikwik',
                    reference_id=txn_id,
                    partner=parkpe,
                )
            except Exception:
                pass
            angular_response = {
                "success": True,
                "transactionId": txn_id,
                "billId": bill_id,
                "receiptNumber": txn_id,
                "amount": amount_float,
                "status": result.get("status") or "SUBMITTED",
                "timestamp": None,
                "message": "Payment submitted",
            }
            vendor_resp_id = _vendor_response_id_from_result(result, "pay_bill") or txn_id
            log_parkpe(
                "parkpe_bbps", "Pay bill success", True, request,
                extra_data={"operator_id": operator_id, "transaction_id": txn_id, "payment_method": payment_method, "vendor_response_id": vendor_resp_id},
                request_method="POST",
                request_body=body,
                response_status=status.HTTP_200_OK,
                response_body=angular_response,
            )
            return Response(angular_response)
        except Exception as e:
            logger.exception(
                "parkpe_bbps_pay unexpected_error",
                extra_data={"operator_id": operator_id, "ref_id": ref_id, "payment_method": payment_method, "error": str(e)},
            )
            if payment_method == "voucher" and voucher_redeemed and voucher is not None and amount_decimal is not None:
                try:
                    from django.db import transaction as db_transaction
                    from django.utils import timezone
                    from portal.models import GiftVoucher, GiftVoucherTransaction, ParkPeVoucherTransaction
                    with db_transaction.atomic():
                        v = GiftVoucher.objects.select_for_update().get(id=voucher.id)
                        before = v.current_balance
                        after = before + amount_decimal
                        v.current_balance = after
                        v.last_transaction_at = timezone.now()
                        if after == 0:
                            v.status = 'FULLY_REDEEMED'
                        elif after < v.original_amount:
                            v.status = 'PARTIALLY_REDEEMED'
                        else:
                            v.status = 'ACTIVE'
                        v.save(update_fields=["current_balance", "last_transaction_at", "status"])
                        GiftVoucherTransaction.objects.create(
                            voucher=v,
                            transaction_type='REDEMPTION',
                            transaction_amount=amount_decimal,
                            balance_before=before,
                            balance_after=after,
                            redemption_method='PIN',
                            transaction_status='SUCCESS',
                            transaction_ref=generate_transaction_id(),
                            metadata={
                                "rollback_for": ref_id,
                                "debit_ref": voucher_debit_ref,
                                "reason": "unexpected_error",
                                "type": "BBPS_ROLLBACK",
                            },
                        )
                        ParkPeVoucherTransaction.objects.create(
                            user=user,
                            amount=amount_decimal,
                            transaction_type=ParkPeVoucherTransaction.CREDIT,
                            balance_after=None,
                            reference_id=ref_id,
                            service_code="BBPS",
                            description=bbps_rollback_description,
                        )
                except Exception:
                    logger.exception("parkpe_bbps_pay rollback_failed_unexpected_error", extra_data={"ref_id": ref_id})
            return Response(
                {"detail": "Payment failed due to an unexpected error. If voucher was debited, it will be restored shortly."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# Favorites and Saved bills (DB-backed, sync across devices)
# ---------------------------------------------------------------------------


class BBPSFavoritesListView(APIView):
    """GET /api/bbps/favorites/ – list. POST /api/bbps/favorites/ – add (idempotent)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        from portal.models import ParkPeBBPSFavoriteBiller
        qs = ParkPeBBPSFavoriteBiller.objects.filter(user=request.user).order_by('-created_at')
        items = [
            {
                "operatorId": f.operator_id,
                "operatorName": f.operator_name or "Biller",
                "category": f.category or "",
                "mobikwikOpId": _resolve_mobikwik_op_id(f.operator_id),
            }
            for f in qs
        ]
        return Response(items)

    def post(self, request):
        body = request.data or {}
        operator_id = str(body.get("operatorId") or body.get("operator_id") or "").strip()
        if not operator_id:
            return Response(
                {"detail": "operatorId is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from portal.models import ParkPeBBPSFavoriteBiller
        obj, created = ParkPeBBPSFavoriteBiller.objects.get_or_create(
            user=request.user,
            operator_id=operator_id,
            defaults={
                "operator_name": str(body.get("operatorName") or body.get("operator_name") or "Biller")[:255],
                "category": str(body.get("category") or "")[:64],
            },
        )
        if not created:
            obj.operator_name = str(body.get("operatorName") or body.get("operator_name") or obj.operator_name)[:255]
            obj.category = str(body.get("category") or obj.category)[:64]
            obj.save(update_fields=["operator_name", "category"])
        return Response({
            "operatorId": obj.operator_id,
            "operatorName": obj.operator_name or "Biller",
            "category": obj.category or "",
            "mobikwikOpId": _resolve_mobikwik_op_id(obj.operator_id),
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class BBPSFavoriteDeleteView(APIView):
    """DELETE /api/bbps/favorites/<operator_id>/ – remove favorite."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def delete(self, request, operator_id):
        from portal.models import ParkPeBBPSFavoriteBiller
        deleted, _ = ParkPeBBPSFavoriteBiller.objects.filter(
            user=request.user,
            operator_id=operator_id,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT if deleted else status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Pay cart (multiple bills, voucher only, total ≤ 10,000)
# ---------------------------------------------------------------------------

CART_MAX_TOTAL = 10_000.0


class BBPSPayCartView(APIView):
    """POST /api/bbps/pay-cart/ – body: bills: [{ billId, operatorId, consumerId, amount }], voucher_id, pin. Voucher only; total ≤ 10,000."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        body = request.data or {}
        bills = body.get("bills")
        if not isinstance(bills, list) or len(bills) == 0:
            return Response(
                {"detail": "bills (non-empty array) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        voucher_id = body.get("voucher_id")
        pin = body.get("pin")
        if voucher_id is None or not str(pin or "").strip():
            return Response(
                {"detail": "voucher_id and pin are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            voucher_id = int(voucher_id)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid voucher_id."}, status=status.HTTP_400_BAD_REQUEST)

        # Normalise and validate each bill; compute total
        total = 0.0
        normalised = []
        for i, b in enumerate(bills):
            if not isinstance(b, dict):
                return Response({"detail": f"bills[{i}] must be an object."}, status=status.HTTP_400_BAD_REQUEST)
            op_id = str(b.get("operatorId") or b.get("operator_id") or "").strip()
            consumer_id = str(b.get("consumerId") or b.get("consumer_id") or "").strip()
            amount = b.get("amount")
            if not op_id or not consumer_id or amount is None:
                return Response(
                    {"detail": f"bills[{i}]: operatorId, consumerId and amount are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                amt = float(amount)
            except (TypeError, ValueError):
                return Response({"detail": f"bills[{i}]: invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
            if amt <= 0:
                return Response({"detail": f"bills[{i}]: amount must be positive."}, status=status.HTTP_400_BAD_REQUEST)
            bill_id = str(b.get("billId") or b.get("bill_id") or generate_transaction_id())
            total += amt
            normalised.append({
                "operatorId": op_id,
                "consumerId": consumer_id,
                "amount": amt,
                "billId": bill_id,
            })
        if total > CART_MAX_TOTAL:
            return Response(
                {"detail": f"Cart total must not exceed ₹{int(CART_MAX_TOTAL):,}. Current total: ₹{total:,.2f}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        from decimal import Decimal
        from portal.models import GiftVoucher, ParkPeVoucherTransaction
        from portal.services.parkpe_voucherx_bridge import get_parkpe_brand_id
        from portal.services.voucher_service import VoucherService
        from django.db import transaction as db_transaction

        brand_id = get_parkpe_brand_id()
        if not brand_id:
            return Response(
                {"detail": "Voucher service not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        voucher = (
            GiftVoucher.objects.filter(
                id=voucher_id,
                brand_id=brand_id,
                metadata__parkpe_user_id=user.pk,
                status__in=["ACTIVE", "PARTIALLY_REDEEMED"],
                current_balance__gte=total,
            )
            .first()
        )
        if not voucher:
            return Response(
                {"detail": "Voucher not found or insufficient balance for cart total."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        service = BBPSService(vendor="mobikwik")
        if not service.is_available():
            return Response(
                {"detail": "BBPS service is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Submit all bills to Mobikwik first; only then debit voucher (all-or-nothing)
        results = []
        for item in normalised:
            op_id_api = _resolve_operator_id_for_mobikwik(item["operatorId"])
            result = service.pay_bill(
                operator_id=op_id_api,
                customer_id=item["consumerId"],
                amount=str(item["amount"]),
                ref_id=item["billId"],
                subscriber_id=None,
                extra=None,
            )
            if not result.get("success"):
                logger.warning(
                    "parkpe_bbps_pay_cart bill failed",
                    extra_data={"operator_id": item["operatorId"], "message": result.get("message")},
                )
                return Response(
                    {"detail": result.get("message", "Payment failed for one or more bills."), "results": results},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            txn_id = result.get("transaction_id") or item["billId"]
            results.append({
                "billId": item["billId"],
                "operatorId": item["operatorId"],
                "consumerId": item["consumerId"],
                "amount": item["amount"],
                "transactionId": txn_id,
                "status": result.get("status") or "SUBMITTED",
            })

        # All Mobikwik calls succeeded; debit voucher once for total
        amount_decimal = Decimal(str(total))
        ref_id = normalised[0]["billId"]
        try:
            VoucherService().redeem_voucher_pin(
                voucher_code=voucher.voucher_code,
                pin=str(pin).strip(),
                amount=amount_decimal,
                transaction_ref=ref_id,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        with db_transaction.atomic():
            ParkPeVoucherTransaction.objects.create(
                user=user,
                amount=amount_decimal,
                transaction_type=ParkPeVoucherTransaction.DEBIT,
                balance_after=None,
                reference_id=ref_id,
                service_code="BBPS",
                description=f"BBPS pay-cart {len(normalised)} bills",
            )

        logger.info(
            "parkpe_bbps_pay_cart success",
            extra_data={"bills_count": len(results), "total": total},
        )
        try:
            from portal.services.hub_income_service import record_hub_income
            from portal.models import ResellerPartner
            parkpe = ResellerPartner.objects.filter(partner_code='parkpe').first()
            record_hub_income(
                'bbps',
                transaction_amount=amount_decimal,
                vendor_code='mobikwik',
                reference_id=ref_id,
                partner=parkpe,
            )
        except Exception:
            pass
        return Response({
            "success": True,
            "message": "All bills paid successfully.",
            "total": total,
            "results": results,
        })


class BBPSSavedBillsListView(APIView):
    """GET /api/bbps/saved-bills/ – list. POST /api/bbps/saved-bills/ – add. Shape compatible with frontend SavedBill."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        from portal.models import ParkPeBBPSSavedBill
        qs = ParkPeBBPSSavedBill.objects.filter(user=request.user).order_by("-created_at")[:50]
        items = [
            {
                "id": str(b.id),
                "nickname": b.nickname or "",
                "operatorId": b.operator_id,
                "operatorName": b.operator_name or "",
                "category": b.category or "",
                "mobikwikOpId": _resolve_mobikwik_op_id(b.operator_id),
                "consumerId": b.consumer_id,
                "lastAmount": float(b.last_amount) if b.last_amount is not None else None,
                "billId": b.bill_id,
                "createdAt": b.created_at.isoformat() if b.created_at else "",
            }
            for b in qs
        ]
        return Response(items)

    def post(self, request):
        body = request.data or {}
        operator_id = str(body.get("operatorId") or body.get("operator_id") or "").strip()
        operator_name = str(body.get("operatorName") or body.get("operator_name") or "Biller")[:255]
        category = str(body.get("category") or "")[:64]
        consumer_id = str(body.get("consumerId") or body.get("consumer_id") or "").strip()
        if not operator_id or not consumer_id:
            return Response(
                {"detail": "operatorId and consumerId are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        nickname = str(body.get("nickname") or "")[:128]
        last_amount = body.get("lastAmount") or body.get("last_amount")
        if last_amount is not None:
            try:
                from decimal import Decimal
                last_amount = Decimal(str(last_amount))
            except Exception:
                last_amount = None
        else:
            last_amount = None
        bill_id = body.get("billId") or body.get("bill_id")
        bill_id = str(bill_id)[:128] if bill_id is not None else None
        from portal.models import ParkPeBBPSSavedBill
        obj = ParkPeBBPSSavedBill.objects.create(
            user=request.user,
            nickname=nickname,
            operator_id=operator_id,
            operator_name=operator_name,
            category=category,
            consumer_id=consumer_id,
            last_amount=last_amount,
            bill_id=bill_id,
        )
        return Response(
            {
                "id": str(obj.id),
                "nickname": obj.nickname or "",
                "operatorId": obj.operator_id,
                "operatorName": obj.operator_name or "",
                "category": obj.category or "",
                "mobikwikOpId": _resolve_mobikwik_op_id(obj.operator_id),
                "consumerId": obj.consumer_id,
                "lastAmount": float(obj.last_amount) if obj.last_amount is not None else None,
                "billId": obj.bill_id,
                "createdAt": obj.created_at.isoformat() if obj.created_at else "",
            },
            status=status.HTTP_201_CREATED,
        )


class BBPSSavedBillUpdateView(APIView):
    """PATCH /api/bbps/saved-bills/<id>/ – body: nickname – update nickname only."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def patch(self, request, pk):
        from portal.models import ParkPeBBPSSavedBill
        try:
            obj = ParkPeBBPSSavedBill.objects.get(user=request.user, pk=pk)
        except ParkPeBBPSSavedBill.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        body = request.data or {}
        nickname = body.get("nickname")
        if nickname is not None:
            obj.nickname = str(nickname)[:128]
            obj.save(update_fields=["nickname"])
        return Response({
            "id": str(obj.id),
            "nickname": obj.nickname or "",
            "operatorId": obj.operator_id,
            "operatorName": obj.operator_name or "",
            "category": obj.category or "",
            "mobikwikOpId": _resolve_mobikwik_op_id(obj.operator_id),
            "consumerId": obj.consumer_id,
            "lastAmount": float(obj.last_amount) if obj.last_amount is not None else None,
            "billId": obj.bill_id,
            "createdAt": obj.created_at.isoformat() if obj.created_at else "",
        })


class BBPSSavedBillDeleteView(APIView):
    """DELETE /api/bbps/saved-bills/<id>/ – remove saved bill."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def delete(self, request, pk):
        from portal.models import ParkPeBBPSSavedBill
        deleted, _ = ParkPeBBPSSavedBill.objects.filter(user=request.user, pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT if deleted else status.HTTP_404_NOT_FOUND)
