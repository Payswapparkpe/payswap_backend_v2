"""
Parkpe API – dashboard summary and payment transactions.
Requires JWT (Authorization: Bearer <token>). Returns shapes expected by Angular.
ParkPe has no wallet: voucher balance only (credit on buy voucher, debit on pay with voucher).
"""
import base64
import hashlib
import hmac
import json
import secrets
import logging
import re
from datetime import datetime, date, timedelta
from decimal import Decimal
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from django.urls import reverse
from django.http import HttpResponse, StreamingHttpResponse

from django.db import DatabaseError, transaction
from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django.contrib.auth import get_user_model
from core.config import get_cashfree_pg_credentials, get_parkpe_backend_secret, payswap_config
from portal.models import (
    BillingDocument,
    GiftVoucher,
    GiftVoucherTransaction,
    DevicePushToken,
    ParkPePaymentGatewayConfig,
    ParkPePaymentOrder,
    ParkPeServiceConfig,
    ParkPeVoucherTransaction,
    Profile,
    NotificationBanner,
    NotificationDeliveryLog,
    UserNotification,
    Profile,
    Vehicle,
    VehicleQRCode,
    VehicleRCData,
    ConnectCallLog,
    ConnectReport,
    ConnectScanLog,
    LogEntry,
    FleetWorkspaceInterest,
    FleetDriverRoster,
)
from portal.services.parkpe_voucherx_bridge import (
    get_parkpe_brand_id,
    credit_voucher_balance,
    get_parkpe_purchase_voucher_summary,
    display_voucher_code_for_api,
)
from portal.services.bbps_service import BBPSService
from portal.services.notification_service_v2 import NotificationServiceV2
from portal.services.notification_events import emit_notification_event
from portal.services.pincode_service import fetch_by_pincode
from portal.utils.transaction_id import generate_transaction_id
from portal.utils.encryption import decrypt_data
from portal.utils.logging_helper import get_logger
from portal.utils.phone_utils import format_phone_display, normalize_phone_number, phone_lookup_candidates
from portal.utils.voucher_utils import unformat_voucher_code
from portal.services.voucher_service import VoucherService
from portal.services.cashfree_vehicle_rc import fetch_vehicle_rc
from api.connect.serializers import VehicleCreateSerializer
from api.connect.views.vehicle_views import _normalize_registration
from api.utils.client_ip import get_client_ip

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
    """GET /api/dashboard/summary – FASTag balance from primary Connect vehicle (BBPS View Bill cache), not retailer wallet."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        fastag_balance = 0.0
        try:
            try:
                from portal.models import Vehicle

                primary = (
                    Vehicle.objects.filter(
                        user=request.user,
                        connect_scope=Vehicle.SCOPE_CONSUMER,
                        is_primary=True,
                    )
                    .only("fastag_balance_last_value")
                    .first()
                )
                if primary and primary.fastag_balance_last_value is not None:
                    fastag_balance = float(primary.fastag_balance_last_value)
            except Exception as e:
                logger.warning("parkpe_dashboard_fastag_primary_failed", extra_data={"error": str(e)})
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


class FleetControlCenterView(APIView):
    """GET /api/dashboard/fleet/control-center – KPI + alerts + module cards for fleet workspace."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        now = timezone.now()
        since_24h = now - timedelta(hours=24)
        today = now.date()

        scope_ids = _fleet_vehicle_owner_user_ids_for_scope(request.user)
        active_vehicles = Vehicle.objects.filter(
            user_id__in=scope_ids,
            connect_scope=Vehicle.SCOPE_FLEET,
        ).count()
        trips_today = ConnectScanLog.objects.filter(
            created_at__date=today,
            vehicle__user_id__in=scope_ids,
            vehicle__connect_scope=Vehicle.SCOPE_FLEET,
        ).count()
        fleet_vid_qs = Vehicle.objects.filter(
            user_id__in=scope_ids,
            connect_scope=Vehicle.SCOPE_FLEET,
        ).values_list("pk", flat=True)
        calls_24h_qs = ConnectCallLog.objects.filter(
            created_at__gte=since_24h,
            vehicle_id__in=fleet_vid_qs,
        )
        calls_total = calls_24h_qs.count()
        calls_success = calls_24h_qs.filter(success=True).count()
        on_time_rate = round((calls_success / calls_total) * 100, 1) if calls_total else 100.0

        pending_reports = ConnectReport.objects.filter(status="pending").count()
        risk_blocks_24h = LogEntry.objects.filter(
            timestamp__gte=since_24h,
            category="connect_vehicle",
            message__icontains="blocked_by_risk_engine",
        ).count()
        active_blocks = Profile.objects.filter(connect_blocked_until__gt=now).count()
        open_alerts = pending_reports + risk_blocks_24h + active_blocks

        top_reported = list(
            ConnectReport.objects.filter(created_at__gte=since_24h)
            .values("reported_user_id")
            .annotate(total=Count("id"))
            .order_by("-total")[:3]
        )
        priority_alerts = [
            f"Pending moderation reports: {pending_reports}",
            f"Risk-engine blocks in last 24h: {risk_blocks_24h}",
            f"Currently blocked users: {active_blocks}",
        ]
        if top_reported:
            top_total = top_reported[0].get("total", 0)
            priority_alerts.append(f"Top reported profile received {top_total} reports in last 24h")

        data = {
            "kpis": [
                {"label": "Active Vehicles", "value": active_vehicles, "trend": "live"},
                {"label": "Trips Today", "value": trips_today, "trend": "today"},
                {"label": "On-time Rate", "value": f"{on_time_rate}%", "trend": "24h"},
                {"label": "Open Alerts", "value": open_alerts, "trend": "live"},
            ],
            "priorityAlerts": priority_alerts,
            "modules": [
                {
                    "title": "Fleet Ops",
                    "description": "Dispatch board, trip monitoring, and route adherence.",
                    "route": "/fleet/trips",
                    "cta": "Open Fleet Ops",
                },
                {
                    "title": "Vehicles",
                    "description": "Vehicle master, RC health, and uptime readiness.",
                    "route": "/fleet/vehicles",
                    "cta": "Manage Vehicles",
                },
                {
                    "title": "Drivers",
                    "description": "Driver roster, risk behavior, and performance snapshot.",
                    "route": "/fleet/drivers",
                    "cta": "Open Driver Hub",
                },
                {
                    "title": "Notification Center",
                    "description": "Broadcast updates, route alerts, and escalations to fleet users.",
                    "route": "/notifications",
                    "cta": "Open Notifications",
                },
                {
                    "title": "Payments & Settlement",
                    "description": "Voucher and payment workflows for fleet operations.",
                    "route": "/payment/history",
                    "cta": "Open Payments",
                },
                {
                    "title": "Compliance & Governance",
                    "description": "Policies, approvals, and operational audit controls.",
                    "route": "/fleet/compliance",
                    "cta": "Open Settings",
                },
            ],
        }
        return Response(data)


def _parse_any_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_profile(user):
    try:
        return user.profile
    except Exception:
        return None


def _safe_vehicle_rc(vehicle):
    try:
        return vehicle.rc_data
    except Exception:
        return None


def _compliance_state_from_rc(rc):
    if not rc:
        return "missing_rc"
    ins = _parse_any_date(getattr(rc, "vehicle_insurance_upto", None))
    puc = _parse_any_date(getattr(rc, "pucc_upto", None))
    today = timezone.now().date()
    if (ins and ins < today) or (puc and puc < today):
        return "expired"
    if (ins and (ins - today).days <= 30) or (puc and (puc - today).days <= 30):
        return "expiring"
    if ins or puc:
        return "compliant"
    return "missing_dates"


_FLEET_ROSTER_BLOCKED_DRIVER_ROLES = frozenset({"super_admin", "admin", "employee"})


def _fleet_vehicle_item_dict(v, scans_24h: int, calls_24h: int) -> dict:
    profile = _safe_profile(v.user)
    rc = _safe_vehicle_rc(v)
    return {
        "id": v.id,
        "ownerUserId": v.user_id,
        "registrationNumber": v.registration_number,
        "vehicleType": v.vehicle_type,
        "brand": v.brand,
        "model": v.model,
        "year": v.year,
        "isPrimary": v.is_primary,
        "ownerName": (profile.full_name if profile else v.user.username) or v.user.username,
        "ownerPhone": (profile.phone if profile else "") or "",
        "scans24h": scans_24h,
        "calls24h": calls_24h,
        "complianceState": _compliance_state_from_rc(rc),
        "insuranceUpto": getattr(rc, "vehicle_insurance_upto", None) if rc else None,
        "pucUpto": getattr(rc, "pucc_upto", None) if rc else None,
        "createdAt": v.created_at.isoformat() if v.created_at else None,
    }


def _parkpe_user_can_delegate_fleet_vehicles(user) -> bool:
    rc = (getattr(user, "role_code", "") or "").strip().lower()
    return rc in ("fleet_admin", "fleet_manager")


def _fleet_vehicle_owner_user_ids_for_scope(user):
    ids = [user.id]
    if _parkpe_user_can_delegate_fleet_vehicles(user):
        ids.extend(
            FleetDriverRoster.objects.filter(manager=user).values_list("driver_id", flat=True)
        )
    return list(dict.fromkeys(ids))


def _serialize_roster_driver_user(u):
    prof = _safe_profile(u)
    return {
        "userId": u.pk,
        "username": u.username,
        "name": (prof.full_name if prof else u.username) or u.username,
        "phone": (prof.phone if prof else "") or "",
    }


def _roster_driver_users_for_manager(manager):
    driver_ids = FleetDriverRoster.objects.filter(manager=manager).values_list("driver_id", flat=True)
    return User.objects.filter(pk__in=list(driver_ids)).select_related("profile").order_by("username")


def _resolve_vehicle_owner_for_fleet_create(request):
    """Returns (owner_user, error_response_or_none)."""
    raw = request.data.get("owner_user_id")
    if raw is None:
        raw = request.data.get("ownerUserId")
    if raw is None or raw == "":
        return request.user, None
    try:
        oid = int(raw)
    except (TypeError, ValueError):
        return None, Response({"detail": "Invalid owner user id."}, status=status.HTTP_400_BAD_REQUEST)
    if oid == request.user.id:
        return request.user, None
    if not _parkpe_user_can_delegate_fleet_vehicles(request.user):
        return None, Response(
            {
                "detail": "Only fleet admin or fleet manager may register vehicles for other drivers.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    if not FleetDriverRoster.objects.filter(manager=request.user, driver_id=oid).exists():
        return None, Response(
            {
                "detail": "That driver is not on your fleet roster. Add them under Fleet roster first.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    owner = User.objects.filter(pk=oid).first()
    if not owner:
        return None, Response({"detail": "Driver user not found."}, status=status.HTTP_404_NOT_FOUND)
    return owner, None


def _resolve_user_for_roster_link(request):
    """Exactly one of driver_user_id, username, phone. Returns (user, error_response)."""
    body = request.data
    uid = body.get("driver_user_id")
    if uid is None:
        uid = body.get("driverUserId")
    uname = (body.get("username") or "").strip()
    phone_raw = (body.get("phone") or "").strip()
    parts = [
        1 if uid not in (None, "") else 0,
        1 if uname else 0,
        1 if phone_raw else 0,
    ]
    if sum(parts) != 1:
        return None, Response(
            {"detail": "Send exactly one of: driver_user_id, username, or phone."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if uid not in (None, ""):
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            return None, Response({"detail": "Invalid driver_user_id."}, status=status.HTTP_400_BAD_REQUEST)
        u = User.objects.filter(pk=uid).first()
        if not u:
            return None, Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return u, None
    if uname:
        u = User.objects.filter(username__iexact=uname).first()
        if not u:
            return None, Response({"detail": "No user with that username."}, status=status.HTTP_404_NOT_FOUND)
        return u, None
    try:
        norm = normalize_phone_number(phone_raw)
    except ValueError:
        return None, Response({"detail": "Invalid phone number."}, status=status.HTTP_400_BAD_REQUEST)
    user_obj = None
    for cand in phone_lookup_candidates(norm):
        prof = Profile.objects.select_related("user").filter(phone=cand).first()
        if prof:
            user_obj = prof.user
            break
    if not user_obj:
        last10 = "".join(c for c in phone_raw if c.isdigit())[-10:]
        if len(last10) == 10:
            prof = (
                Profile.objects.select_related("user")
                .filter(phone__endswith=last10)
                .first()
            )
            if prof:
                user_obj = prof.user
    if not user_obj:
        return None, Response(
            {"detail": "No profile found with that phone number."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return user_obj, None


class FleetVehiclesView(APIView):
    """GET/POST /api/dashboard/fleet/vehicles — fleet workspace vehicles for the logged-in user."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        page = max(_safe_int(request.GET.get("page"), 1), 1)
        limit = min(max(_safe_int(request.GET.get("limit"), 20), 1), 100)
        search = (request.GET.get("search") or "").strip()
        vehicle_type = (request.GET.get("vehicle_type") or "").strip().lower()

        scope_ids = _fleet_vehicle_owner_user_ids_for_scope(request.user)
        qs = (
            Vehicle.objects.filter(user_id__in=scope_ids, connect_scope=Vehicle.SCOPE_FLEET)
            .select_related("user__profile", "rc_data")
            .order_by("-created_at")
        )
        if search:
            qs = qs.filter(
                Q(registration_number__icontains=search)
                | Q(brand__icontains=search)
                | Q(model__icontains=search)
                | Q(user__profile__first_name__icontains=search)
                | Q(user__profile__last_name__icontains=search)
            )
        if vehicle_type:
            qs = qs.filter(vehicle_type=vehicle_type)

        total = qs.count()
        start = (page - 1) * limit
        vehicles = list(qs[start : start + limit])
        since_24h = timezone.now() - timedelta(hours=24)
        vehicle_ids = [v.id for v in vehicles]

        scans_24h_map = {
            row["vehicle_id"]: row["total"]
            for row in ConnectScanLog.objects.filter(vehicle_id__in=vehicle_ids, created_at__gte=since_24h)
            .values("vehicle_id")
            .annotate(total=Count("id"))
        }
        calls_24h_map = {
            row["vehicle_id"]: row["total"]
            for row in ConnectCallLog.objects.filter(vehicle_id__in=vehicle_ids, created_at__gte=since_24h)
            .values("vehicle_id")
            .annotate(total=Count("id"))
        }

        items = [
            _fleet_vehicle_item_dict(v, scans_24h_map.get(v.id, 0), calls_24h_map.get(v.id, 0))
            for v in vehicles
        ]

        can_delegate = _parkpe_user_can_delegate_fleet_vehicles(request.user)
        roster_payload = []
        if can_delegate:
            roster_payload = [_serialize_roster_driver_user(u) for u in _roster_driver_users_for_manager(request.user)]

        return Response(
            {
                "items": items,
                "total": total,
                "page": page,
                "limit": limit,
                "canDelegateToDrivers": can_delegate,
                "rosterDrivers": roster_payload,
            }
        )

    def post(self, request):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if request.data.get("accept_ownership_declaration") is not True:
            return Response(
                {"detail": "You must accept the vehicle ownership declaration to add a vehicle."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        owner, err = _resolve_vehicle_owner_for_fleet_create(request)
        if err is not None:
            return err
        data = request.data.copy()
        data["user"] = owner.id
        serializer = VehicleCreateSerializer(data=data, partial=False)
        serializer.is_valid(raise_exception=True)
        reg = (serializer.validated_data.get("registration_number") or "").strip().upper()
        reg_norm = _normalize_registration(reg)
        if Vehicle.objects.filter(
            user=owner,
            registration_number_normalized=reg_norm,
            connect_scope=Vehicle.SCOPE_FLEET,
        ).exists():
            return Response(
                {"detail": "A vehicle with this registration number already exists for this owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        vehicle = serializer.save(
            user=owner,
            ownership_declaration_accepted_at=timezone.now(),
            connect_scope=Vehicle.SCOPE_FLEET,
        )
        if Vehicle.objects.filter(user=owner, connect_scope=Vehicle.SCOPE_FLEET).count() == 1:
            vehicle.is_primary = True
            vehicle.save(update_fields=["is_primary"])
        code = secrets.token_urlsafe(10).replace("-", "").replace("_", "")[:14]
        while VehicleQRCode.objects.filter(code=code).exists():
            code = secrets.token_urlsafe(10).replace("-", "").replace("_", "")[:14]
        VehicleQRCode.objects.create(vehicle=vehicle, code=code)
        vehicle_count = Vehicle.objects.filter(user=owner, connect_scope=Vehicle.SCOPE_FLEET).count()
        if vehicle_count == 1:
            try:
                rc_response, rc_reason, rc_details = fetch_vehicle_rc(reg)
                if rc_response:
                    VehicleRCData.objects.update_or_create(
                        vehicle=vehicle,
                        defaults={"raw_response": rc_response},
                    )
                else:
                    logger.info(
                        "fleet_vehicle_create_rc_no_data vehicle_id=%s reg=%s reason=%s",
                        vehicle.pk,
                        reg,
                        rc_reason,
                    )
            except Exception as e:
                logger.warning(
                    "fleet_vehicle_create_rc_exception",
                    extra={"vehicle_id": vehicle.pk, "reg": reg, "error": str(e)},
                )
        vehicle = (
            Vehicle.objects.filter(pk=vehicle.pk)
            .select_related("user__profile", "rc_data")
            .first()
        )
        since_24h = timezone.now() - timedelta(hours=24)
        scans_n = ConnectScanLog.objects.filter(vehicle_id=vehicle.pk, created_at__gte=since_24h).count()
        calls_n = ConnectCallLog.objects.filter(vehicle_id=vehicle.pk, created_at__gte=since_24h).count()
        payload = _fleet_vehicle_item_dict(vehicle, scans_n, calls_n)
        return Response(payload, status=status.HTTP_201_CREATED)


class FleetDriverRosterView(APIView):
    """GET/POST /api/dashboard/fleet/roster — list or add drivers a fleet admin/manager may register vehicles for."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        can = _parkpe_user_can_delegate_fleet_vehicles(request.user)
        drivers = (
            [_serialize_roster_driver_user(u) for u in _roster_driver_users_for_manager(request.user)]
            if can
            else []
        )
        return Response({"canDelegateToDrivers": can, "rosterDrivers": drivers})

    def post(self, request):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _parkpe_user_can_delegate_fleet_vehicles(request.user):
            return Response(
                {"detail": "Only fleet admin or fleet manager may manage the driver roster."},
                status=status.HTTP_403_FORBIDDEN,
            )
        driver_user, err = _resolve_user_for_roster_link(request)
        if err is not None:
            return err
        if driver_user.id == request.user.id:
            return Response(
                {"detail": "You cannot add yourself as a roster driver."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rc = (getattr(driver_user, "role_code", "") or "").strip().lower()
        if rc in _FLEET_ROSTER_BLOCKED_DRIVER_ROLES:
            return Response(
                {"detail": "This account type cannot be added as a fleet driver."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if FleetDriverRoster.objects.filter(manager=request.user, driver=driver_user).exists():
            return Response(
                {"detail": "This driver is already on your roster."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        FleetDriverRoster.objects.create(manager=request.user, driver=driver_user)
        return Response(_serialize_roster_driver_user(driver_user), status=status.HTTP_201_CREATED)


class FleetDriverRosterUnlinkView(APIView):
    """DELETE /api/dashboard/fleet/roster/<driver_id> — remove a driver from roster."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, driver_id):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _parkpe_user_can_delegate_fleet_vehicles(request.user):
            return Response(
                {"detail": "Only fleet admin or fleet manager may manage the driver roster."},
                status=status.HTTP_403_FORBIDDEN,
            )
        deleted, _ = FleetDriverRoster.objects.filter(manager=request.user, driver_id=driver_id).delete()
        if not deleted:
            return Response({"detail": "Roster entry not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FleetDriversView(APIView):
    """GET /api/dashboard/fleet/drivers"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        page = max(_safe_int(request.GET.get("page"), 1), 1)
        limit = min(max(_safe_int(request.GET.get("limit"), 20), 1), 100)
        search = (request.GET.get("search") or "").strip()
        qs = Profile.objects.select_related("user").filter(
            user__connect_vehicles__connect_scope=Vehicle.SCOPE_FLEET,
        ).distinct()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
            )
        total = qs.count()
        start = (page - 1) * limit
        profiles = list(qs.order_by("first_name", "last_name")[start : start + limit])
        user_ids = [p.user_id for p in profiles]
        since_24h = timezone.now() - timedelta(hours=24)

        vehicles_map = {
            row["user_id"]: row["total"]
            for row in Vehicle.objects.filter(
                user_id__in=user_ids,
                connect_scope=Vehicle.SCOPE_FLEET,
            ).values("user_id").annotate(total=Count("id"))
        }
        reports_map = {
            row["reported_user_id"]: row["total"]
            for row in ConnectReport.objects.filter(reported_user_id__in=user_ids, created_at__gte=since_24h)
            .values("reported_user_id")
            .annotate(total=Count("id"))
        }
        scans_map = {
            row["scanned_by_id"]: row["total"]
            for row in ConnectScanLog.objects.filter(scanned_by_id__in=user_ids, created_at__gte=since_24h)
            .values("scanned_by_id")
            .annotate(total=Count("id"))
        }

        items = []
        for p in profiles:
            blocked_until = getattr(p, "connect_blocked_until", None)
            items.append(
                {
                    "id": p.user_id,
                    "name": p.full_name or p.user.username,
                    "phone": p.phone,
                    "email": p.email,
                    "city": p.city,
                    "vehiclesCount": vehicles_map.get(p.user_id, 0),
                    "scans24h": scans_map.get(p.user_id, 0),
                    "reportsAgainst24h": reports_map.get(p.user_id, 0),
                    "warningCount": int(getattr(p, "connect_warning_count", 0) or 0),
                    "blockedUntil": blocked_until.isoformat() if blocked_until else None,
                }
            )

        return Response({"items": items, "total": total, "page": page, "limit": limit})


FLEET_MANUAL_SCAN_UA_PREFIX = "ParkPe-Fleet-Manual|"


def _serialize_fleet_trip_log(row: ConnectScanLog) -> dict:
    scanner_profile = _safe_profile(row.scanned_by) if row.scanned_by else None
    ua = row.user_agent or ""
    entry_source = "manual" if ua.startswith(FLEET_MANUAL_SCAN_UA_PREFIX) else "connect"
    return {
        "id": row.id,
        "qrCode": row.qr_code,
        "vehicleId": row.vehicle_id,
        "registrationNumber": getattr(row.vehicle, "registration_number", "") if row.vehicle else "",
        "vehicleType": getattr(row.vehicle, "vehicle_type", "") if row.vehicle else "",
        "scannedBy": (scanner_profile.full_name if scanner_profile else "") if row.scanned_by else "",
        "scannerPhone": (scanner_profile.phone if scanner_profile else "") if row.scanned_by else "",
        "ipAddress": row.ip_address,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "entrySource": entry_source,
    }


class FleetTripsView(APIView):
    """GET/POST /api/dashboard/fleet/trips — list Connect scan logs; POST logs a manual visit (no QR at site)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        page = max(_safe_int(request.GET.get("page"), 1), 1)
        limit = min(max(_safe_int(request.GET.get("limit"), 20), 1), 100)
        date_from = _parse_date_param(request.GET.get("date_from"))
        date_to = _parse_date_param(request.GET.get("date_to"))

        scope_ids = _fleet_vehicle_owner_user_ids_for_scope(request.user)
        qs = ConnectScanLog.objects.select_related("vehicle", "scanned_by__profile").filter(
            vehicle__connect_scope=Vehicle.SCOPE_FLEET,
            vehicle__user_id__in=scope_ids,
        ).order_by("-created_at")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        total = qs.count()
        start = (page - 1) * limit
        rows = list(qs[start : start + limit])
        items = [_serialize_fleet_trip_log(row) for row in rows]

        return Response({"items": items, "total": total, "page": page, "limit": limit})

    def post(self, request):
        """Record a fleet visit manually (same storage as QR scans — shows on trip board)."""
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        raw_vid = request.data.get("vehicleId")
        if raw_vid is None:
            raw_vid = request.data.get("vehicle_id")
        try:
            vehicle_id = int(raw_vid)
        except (TypeError, ValueError):
            return Response(
                {"detail": "vehicle_id is required and must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scope_ids = _fleet_vehicle_owner_user_ids_for_scope(request.user)
        vehicle = (
            Vehicle.objects.filter(
                pk=vehicle_id,
                user_id__in=scope_ids,
                connect_scope=Vehicle.SCOPE_FLEET,
            )
            .select_related("user")
            .first()
        )
        if not vehicle:
            return Response(
                {"detail": "Vehicle not found or not a fleet vehicle in your workspace."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qr_code = VehicleQRCode.objects.filter(vehicle_id=vehicle.pk).values_list("code", flat=True).first()
        if not qr_code:
            qr_code = f"manual:{vehicle.pk}:{int(timezone.now().timestamp())}"
        qr_code = (qr_code or "")[:128]

        notes_raw = request.data.get("notes")
        if notes_raw is None:
            notes_raw = request.data.get("note")
        notes = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(notes_raw or "").strip())[:500]

        ua_parts = [f"{FLEET_MANUAL_SCAN_UA_PREFIX}v={vehicle.pk}", f"by={request.user.pk}"]
        if notes:
            ua_parts.append(f"n={notes}")
        user_agent = "|".join(ua_parts)[:4000]

        client_ip = get_client_ip(request)
        try:
            row = ConnectScanLog.objects.create(
                qr_code=qr_code,
                vehicle=vehicle,
                scanned_by=request.user,
                ip_address=(client_ip or None) if client_ip else None,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.exception("fleet_manual_trip_create_failed", extra_data={"vehicle_id": vehicle_id, "error": str(e)})
            return Response(
                {"detail": "Could not record visit. Try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        row = ConnectScanLog.objects.select_related("vehicle", "scanned_by__profile").get(pk=row.pk)
        logger.info(
            "fleet_manual_trip_created",
            extra_data={"scan_id": row.pk, "vehicle_id": vehicle.pk, "user_id": request.user.pk},
        )
        return Response(_serialize_fleet_trip_log(row), status=status.HTTP_201_CREATED)


class FleetComplianceView(APIView):
    """GET /api/dashboard/fleet/compliance"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        page = max(_safe_int(request.GET.get("page"), 1), 1)
        limit = min(max(_safe_int(request.GET.get("limit"), 20), 1), 100)
        status_filter = (request.GET.get("status") or "").strip().lower()

        scope_ids = _fleet_vehicle_owner_user_ids_for_scope(request.user)
        qs = (
            Vehicle.objects.filter(user_id__in=scope_ids, connect_scope=Vehicle.SCOPE_FLEET)
            .select_related("user__profile", "rc_data")
            .order_by("-created_at")
        )
        vehicles = list(qs)

        filtered = []
        for v in vehicles:
            rc = _safe_vehicle_rc(v)
            compliance = _compliance_state_from_rc(rc)
            if status_filter and compliance != status_filter:
                continue
            profile = _safe_profile(v.user)
            filtered.append(
                {
                    "vehicleId": v.id,
                    "registrationNumber": v.registration_number,
                    "ownerName": (profile.full_name if profile else v.user.username) or v.user.username,
                    "ownerPhone": (profile.phone if profile else "") or "",
                    "insuranceUpto": getattr(rc, "vehicle_insurance_upto", None) if rc else None,
                    "pucUpto": getattr(rc, "pucc_upto", None) if rc else None,
                    "complianceState": compliance,
                }
            )

        total = len(filtered)
        start = (page - 1) * limit
        items = filtered[start : start + limit]
        summary = {
            "compliant": sum(1 for row in filtered if row["complianceState"] == "compliant"),
            "expiring": sum(1 for row in filtered if row["complianceState"] == "expiring"),
            "expired": sum(1 for row in filtered if row["complianceState"] == "expired"),
            "missing_rc": sum(1 for row in filtered if row["complianceState"] == "missing_rc"),
        }
        return Response({"items": items, "summary": summary, "total": total, "page": page, "limit": limit})


class FleetTrendsView(APIView):
    """GET /api/dashboard/fleet/trends?days=7"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _parkpe_user_has_fleet_role(request.user):
            return Response(
                {"detail": "Fleet workspace access required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        days = min(max(_safe_int(request.GET.get("days"), 7), 3), 30)
        now = timezone.now()
        since = now - timedelta(days=days - 1)
        scope_ids = _fleet_vehicle_owner_user_ids_for_scope(request.user)
        fleet_vid_qs = Vehicle.objects.filter(
            user_id__in=scope_ids,
            connect_scope=Vehicle.SCOPE_FLEET,
        ).values_list("pk", flat=True)
        scans = (
            ConnectScanLog.objects.filter(
                created_at__date__gte=since.date(),
                vehicle__user_id__in=scope_ids,
                vehicle__connect_scope=Vehicle.SCOPE_FLEET,
            )
            .values("created_at__date")
            .annotate(total=Count("id"))
        )
        calls = (
            ConnectCallLog.objects.filter(
                created_at__date__gte=since.date(),
                vehicle_id__in=fleet_vid_qs,
            )
            .values("created_at__date")
            .annotate(total=Count("id"), success=Count("id", filter=Q(success=True)))
        )
        reports = (
            ConnectReport.objects.filter(created_at__date__gte=since.date())
            .values("created_at__date")
            .annotate(total=Count("id"))
        )
        scans_map = {str(row["created_at__date"]): row["total"] for row in scans}
        calls_map = {str(row["created_at__date"]): row for row in calls}
        reports_map = {str(row["created_at__date"]): row["total"] for row in reports}

        series = []
        for i in range(days):
            day = since.date() + timedelta(days=i)
            key = str(day)
            call_row = calls_map.get(key, {})
            total_calls = int(call_row.get("total", 0) or 0)
            success_calls = int(call_row.get("success", 0) or 0)
            series.append(
                {
                    "date": key,
                    "label": day.strftime("%a"),
                    "scans": int(scans_map.get(key, 0)),
                    "calls": total_calls,
                    "callSuccessRate": round((success_calls / total_calls) * 100, 1) if total_calls else 0.0,
                    "reports": int(reports_map.get(key, 0)),
                }
            )
        return Response({"series": series, "days": days})


class NotificationBannersView(APIView):
    """GET /api/dashboard/notifications?slot=bbps_right_rail&screen=bbps_category&service=bbps"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        slot = (request.GET.get("slot") or NotificationBanner.SLOT_BBPS_RIGHT_RAIL).strip().lower()
        screen = (request.GET.get("screen") or "").strip().lower()
        service = (request.GET.get("service") or "").strip().lower()
        now = timezone.now()

        q = NotificationBanner.objects.filter(
            is_active=True,
            slot=slot,
            platform__in=[NotificationBanner.PLATFORM_BOTH, NotificationBanner.PLATFORM_PARKPE],
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
        )

        if service:
            q = q.filter(Q(service_code="") | Q(service_code=service))
        if screen:
            q = q.filter(Q(screen_code="") | Q(screen_code=screen))

        banners = [
            {
                "id": row.id,
                "name": row.name,
                "title": row.title,
                "message": row.message,
                "ctaText": row.cta_text,
                "ctaUrl": row.cta_url,
                "imageUrl": row.image_url,
                "bgColor": row.bg_color,
                "textColor": row.text_color,
                "priority": row.priority,
            }
            for row in q.order_by("priority", "-created_at")[:8]
        ]
        return Response({"banners": banners})


class NotificationFeedView(APIView):
    """GET /api/dashboard/notifications/feed?limit=20&offset=0"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(max(int(request.GET.get("limit", 20)), 1), 100)
        offset = max(int(request.GET.get("offset", 0)), 0)
        qs = UserNotification.objects.filter(user=request.user).order_by("-created_at")
        total = qs.count()
        rows = qs[offset : offset + limit]
        out = [
            {
                "id": row.id,
                "title": row.title,
                "message": row.message,
                "channel": row.channel,
                "isRead": row.is_read,
                "readAt": row.read_at.isoformat() if row.read_at else None,
                "deepLink": row.deep_link,
                "metadata": row.metadata or {},
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
        return Response({"items": out, "total": total})


class NotificationUnreadCountView(APIView):
    """GET /api/dashboard/notifications/unread-count"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread = UserNotification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread": unread})


class NotificationReadView(APIView):
    """POST /api/dashboard/notifications/<id>/read"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        row = UserNotification.objects.filter(id=notification_id, user=request.user).first()
        if not row:
            return Response({"detail": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        if not row.is_read:
            row.is_read = True
            row.read_at = timezone.now()
            row.save(update_fields=["is_read", "read_at"])
            NotificationDeliveryLog.objects.filter(
                user=request.user,
                campaign=row.campaign,
                channel=row.channel,
            ).update(status=NotificationDeliveryLog.STATUS_READ, updated_at=timezone.now())
        return Response({"success": True})


class RegisterPushTokenView(APIView):
    """POST /api/dashboard/notifications/push-token"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = str(request.data.get("token") or "").strip()
        if not token:
            return Response({"detail": "token is required."}, status=status.HTTP_400_BAD_REQUEST)
        device_platform = str(request.data.get("devicePlatform") or DevicePushToken.PLATFORM_ANDROID).strip().lower()
        app_platform = str(request.data.get("appPlatform") or NotificationBanner.PLATFORM_PARKPE).strip().lower()
        row, _ = DevicePushToken.objects.update_or_create(
            token=token,
            defaults={
                "user": request.user,
                "device_platform": device_platform,
                "app_platform": app_platform,
                "is_active": True,
                "last_seen_at": timezone.now(),
            },
        )
        return Response({"success": True, "id": row.id})


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


def _parkpe_voucher_txn_by_public_id(user, transaction_id: str) -> ParkPeVoucherTransaction | None:
    """
    Resolve a voucher ledger row by reference_id (e.g. T… ids from generate_transaction_id)
    or by numeric primary key.

    Do not use Q(pk=non_numeric): Django raises ValueError on integer PK fields before the query runs.
    """
    tid = str(transaction_id or "").strip()
    if not tid or not user:
        return None
    txn = ParkPeVoucherTransaction.objects.filter(user=user, reference_id=tid).first()
    if txn is not None:
        return txn
    if tid.isdigit():
        return ParkPeVoucherTransaction.objects.filter(user=user, pk=int(tid)).first()
    return None


def _billing_reference_for_voucher_txn(txn: ParkPeVoucherTransaction) -> str:
    return (txn.reference_id or str(txn.pk)).strip()


def _find_user_billing_document(
    user,
    *,
    reference_id: str,
    service_code: str,
    transaction_direction: str | None = None,
) -> BillingDocument | None:
    ref = (reference_id or "").strip()
    sc = (service_code or "other").strip().lower().replace(" ", "_") or "other"
    if not ref or not user or not getattr(user, "pk", None):
        return None
    # iexact: older rows may have stored service_code casing unlike normalized ledger values.
    base = BillingDocument.objects.filter(user=user, reference_id=ref, service_code__iexact=sc)
    td = (transaction_direction or "").strip().lower()
    if td:
        doc = base.filter(transaction_direction=td).order_by("-issued_at").first()
        if doc:
            return doc
        # Legacy: direction not stored on document when first shipped.
        doc = base.filter(transaction_direction="").order_by("-issued_at").first()
        if doc:
            return doc
    return base.order_by("-issued_at").first()


def _find_billing_linked_to_voucher_txn(txn: ParkPeVoucherTransaction) -> BillingDocument | None:
    """Resolve tax document for a voucher ledger row (reference match + legacy FK-only links)."""
    if not txn or not txn.user_id:
        return None
    sc = (txn.service_code or "other").strip().lower().replace(" ", "_") or "other"
    ref = _billing_reference_for_voucher_txn(txn)
    doc = _find_user_billing_document(
        txn.user,
        reference_id=ref,
        service_code=sc,
        transaction_direction=txn.transaction_type,
    )
    if doc:
        return doc
    return (
        BillingDocument.objects.filter(user=txn.user, parkpe_voucher_transaction_id=txn.pk)
        .order_by("-issued_at")
        .first()
    )


def _tax_api_fields_from_document(doc: BillingDocument) -> dict:
    snap = doc.snapshot or {}
    return {
        "billingDocumentId": doc.pk,
        "taxSnapshot": {
            "documentType": doc.document_type,
            "taxableAmount": float(doc.taxable_amount),
            "cgst": float(doc.cgst_amount),
            "sgst": float(doc.sgst_amount),
            "igst": float(doc.igst_amount),
            "gstTotal": float(doc.gst_total),
            "tdsAmount": float(doc.tds_amount),
            "grandTotal": float(doc.grand_total),
            "sacOrHsn": str(snap.get("sac_or_hsn") or ""),
            "currency": doc.currency or "INR",
        },
    }


def _customer_details_for_user(user) -> dict:
    """Payer identity for receipts, history, and compliance (from Profile)."""
    empty = {"name": "", "email": "", "phone": ""}
    if not user or not getattr(user, "pk", None):
        return empty
    try:
        prof = (
            Profile.objects.filter(user=user)
            .only("first_name", "middle_name", "last_name", "email", "phone")
            .first()
        )
    except Exception:
        return empty
    if not prof:
        return empty
    name = str(prof.full_name or "").strip()
    email = str(prof.email or "").strip()
    phone = str(prof.phone or "").strip()
    return {"name": name, "email": email, "phone": phone}


def _merge_tax_for_voucher_txn(txn: ParkPeVoucherTransaction, out: dict) -> None:
    """Attach taxSnapshot from BillingDocument; create document if missing (idempotent)."""
    if not txn or not txn.user_id:
        return
    user = txn.user
    ref = _billing_reference_for_voucher_txn(txn)
    doc = _find_billing_linked_to_voucher_txn(txn)
    if doc:
        out.update(_tax_api_fields_from_document(doc))
        return
    try:
        from portal.services.billing_document_service import record_billing_from_parkpe_voucher_transaction

        record_billing_from_parkpe_voucher_transaction(txn)
    except Exception:
        logger.exception(
            "parkpe_ensure_voucher_txn_billing_failed",
            extra_data={"reference_id": ref[:120], "user_id": user.pk},
        )
    doc = _find_billing_linked_to_voucher_txn(txn)
    if doc:
        out.update(_tax_api_fields_from_document(doc))


def _merge_tax_for_payment_order(order: ParkPePaymentOrder, user, out: dict) -> None:
    """Attach taxSnapshot for PG voucher top-up; persist BillingDocument when order completed."""
    if not user or not getattr(user, "pk", None):
        return
    oid = str(order.order_id).strip()
    doc = _find_user_billing_document(
        user,
        reference_id=oid,
        service_code="voucher_purchase",
        transaction_direction="credit",
    )
    if doc:
        out.update(_tax_api_fields_from_document(doc))
        return
    if order.status == ParkPePaymentOrder.COMPLETED:
        try:
            from portal.services.billing_document_service import record_voucher_purchase_billing

            record_voucher_purchase_billing(user=user, order_id=oid, amount=order.amount)
        except Exception:
            logger.exception(
                "parkpe_ensure_voucher_purchase_billing_failed",
                extra_data={"order_id": oid[:120], "user_id": user.pk},
            )
        doc = _find_user_billing_document(
            user,
            reference_id=oid,
            service_code="voucher_purchase",
            transaction_direction="credit",
        )
        if doc:
            out.update(_tax_api_fields_from_document(doc))


def _ensure_user_billing_document_exists(user, transaction_id: str) -> None:
    """Create immutable BillingDocument on demand so HTML/PDF receipt and APIs stay aligned."""
    if _resolve_user_billing_document(user, transaction_id):
        return
    tid = str(transaction_id or "").strip()
    if not tid:
        return
    order = ParkPePaymentOrder.objects.filter(user=user, order_id=tid).first()
    if order and order.status == ParkPePaymentOrder.COMPLETED:
        try:
            from portal.services.billing_document_service import record_voucher_purchase_billing

            record_voucher_purchase_billing(user=user, order_id=tid, amount=order.amount)
        except Exception:
            logger.exception(
                "parkpe_receipt_ensure_order_billing_failed",
                extra_data={"order_id": tid[:120], "user_id": user.pk},
            )
        return
    txn = _parkpe_voucher_txn_by_public_id(user, tid)
    if txn:
        try:
            from portal.services.billing_document_service import record_billing_from_parkpe_voucher_transaction

            record_billing_from_parkpe_voucher_transaction(txn)
        except Exception:
            logger.exception(
                "parkpe_receipt_ensure_voucher_billing_failed",
                extra_data={"transaction_id": tid[:120], "user_id": user.pk},
            )


def _resolve_user_billing_document(user, transaction_id: str) -> BillingDocument | None:
    """Resolve BillingDocument for a ParkPe payment history id (order_id, voucher reference, or voucher pk)."""
    tid = str(transaction_id or "").strip()
    if not tid or not user:
        return None
    order = ParkPePaymentOrder.objects.filter(user=user, order_id=tid).first()
    if order:
        return _find_user_billing_document(
            user,
            reference_id=order.order_id,
            service_code="voucher_purchase",
            transaction_direction="credit",
        )
    txn = _parkpe_voucher_txn_by_public_id(user, tid)
    if txn:
        return _find_billing_linked_to_voucher_txn(txn)
    return None


def _render_user_receipt_html(doc: BillingDocument) -> str:
    from portal.services.billing_document_render import billing_document_display_label, render_billing_document_html

    return render_billing_document_html(
        doc,
        heading=f"ParkPe — {billing_document_display_label(doc.document_type)}",
        include_print_hint=True,
    )


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
        "customer": _customer_details_for_user(txn.user),
        "timestamp": txn.created_at.isoformat() if txn.created_at else "",
        "description": description,
        "transactionTypeDirection": txn.transaction_type,  # 'credit' | 'debit'
    }
    if txn.balance_after is not None:
        out["balanceAfter"] = float(txn.balance_after)
    if getattr(txn, "user_id", None):
        _merge_tax_for_voucher_txn(txn, out)
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


def _transaction_from_payment_order(order, user=None):
    """Map ParkPePaymentOrder to Angular Transaction shape (voucher purchases)."""
    status_map = {"completed": "success", "pending": "pending", "failed": "failed"}
    u = user or getattr(order, "user", None)
    out = {
        "id": order.order_id,           # Use order_id consistently (list + detail)
        "orderId": order.order_id,
        "transactionId": order.order_id,
        "transactionType": "voucher_purchase",
        "gateway": "Cashfree",
        "amount": float(order.amount),
        "currency": "INR",
        "status": status_map.get(order.status, "pending"),
        "customer": _customer_details_for_user(u) if u else {"name": "", "email": "", "phone": ""},
        "timestamp": order.created_at.isoformat() if order.created_at else "",
        "description": "Voucher purchase",
        "transactionTypeDirection": "credit",
    }
    if u and getattr(u, "pk", None):
        _merge_tax_for_payment_order(order, u, out)
    return out


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
            t = _transaction_from_payment_order(order, user=user)
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
            return Response(_transaction_from_payment_order(order, user=user))
        # Try voucher transaction by pk or reference_id
        txn = _parkpe_voucher_txn_by_public_id(user, transaction_id)
        if txn:
            return Response(_transaction_from_voucher_txn(txn))
        return Response(
            {"detail": "Transaction not found."},
            status=status.HTTP_404_NOT_FOUND,
        )


class PaymentTransactionReceiptHtmlView(APIView):
    """
    GET /api/payment/transactions/<id>/receipt/
    - Default: HTML receipt in browser.
    - ?download=1 : HTML as attachment.
    - ?format=pdf : PDF attachment (requires xhtml2pdf); otherwise 415 with JSON detail.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        _ensure_user_billing_document_exists(request.user, transaction_id)
        doc = _resolve_user_billing_document(request.user, transaction_id)
        if not doc:
            return HttpResponse(
                "Receipt is not available for this transaction.",
                status=404,
                content_type="text/plain; charset=utf-8",
            )
        fmt = (request.GET.get("format") or "").strip().lower()
        download_flag = (request.GET.get("download") or "").strip().lower() in ("1", "true", "yes")
        html = _render_user_receipt_html(doc)
        if fmt == "pdf":
            from portal.services.billing_document_render import html_to_pdf_bytes, safe_download_filename

            pdf = html_to_pdf_bytes(html)
            if not pdf:
                return Response(
                    {
                        "detail": "PDF is not available on this server. Open the HTML receipt and use Print → Save as PDF.",
                    },
                    status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )
            resp = HttpResponse(pdf, content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="{safe_download_filename(doc, "pdf")}"'
            return resp
        resp = HttpResponse(html, content_type="text/html; charset=utf-8")
        if download_flag:
            resp["Content-Disposition"] = f'attachment; filename="parkpe_receipt_{doc.pk}.html"'
        return resp


class PaymentStatusStreamView(APIView):
    """
    GET /api/payment/stream/status/<order_id>
    Server-sent event endpoint used by frontend realtime watcher.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        safe_order_id = str(order_id or "").strip()
        if not safe_order_id:
            return Response({"detail": "order_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        status_value = "pending"
        order = ParkPePaymentOrder.objects.filter(user=request.user, order_id=safe_order_id).only("status").first()
        if order:
            status_map = {"completed": "success", "failed": "failed", "pending": "pending"}
            status_value = status_map.get(order.status, "pending")
        else:
            if _parkpe_voucher_txn_by_public_id(request.user, safe_order_id):
                status_value = "success"

        payload = json.dumps({"orderId": safe_order_id, "status": status_value})

        def _event_stream():
            yield f"event: payment_status\ndata: {payload}\n\n"

        response = StreamingHttpResponse(_event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


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
        orders_data = []
        for o in orders:
            row = {
                "id": str(o.pk),
                "orderId": o.order_id,
                "amount": float(o.amount),
                "currency": "INR",
                "gateway": o.gateway,
                "status": o.status,
                "referenceId": o.reference_id,
                "createdAt": o.created_at.isoformat() if o.created_at else "",
            }
            tax_payload: dict = {}
            _merge_tax_for_payment_order(o, user, tax_payload)
            if tax_payload.get("taxSnapshot"):
                row["taxSnapshot"] = tax_payload["taxSnapshot"]
            orders_data.append(row)
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
        from portal.services.billing_party_service import (
            billing_address_error_payload,
            parkpe_billing_address_required,
            profile_billing_address_complete,
        )

        if parkpe_billing_address_required():
            profile_gate = getattr(user, "profile", None)
            if not profile_gate and hasattr(user, "profile_set"):
                profile_gate = user.profile_set.first()
            if not profile_billing_address_complete(profile_gate):
                return Response(billing_address_error_payload(), status=status.HTTP_400_BAD_REQUEST)
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
                cf_env = (getattr(payswap_config, "CASHFREE_PG_ENVIRONMENT", None) or "SANDBOX").strip().upper()
                if cf_env not in ("SANDBOX", "PRODUCTION"):
                    cf_env = "SANDBOX"
                return Response({
                    "orderId": cf_order_id,
                    "paymentSessionId": payment_session_id,
                    "amount": float(amount_decimal),
                    "currency": currency,
                    "cashfreeEnvironment": cf_env,
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
    order_amount = None
    issuance_info = None
    with transaction.atomic():
        locked = (
            ParkPePaymentOrder.objects.select_for_update()
            .filter(pk=order.pk, status=ParkPePaymentOrder.PENDING)
            .first()
        )
        if not locked:
            return None
        user = locked.user
        locked.reference_id = payment_id or locked.reference_id
        locked.status = ParkPePaymentOrder.COMPLETED
        locked.save(update_fields=["reference_id", "status", "updated_at"])
        order_amount = locked.amount
        issuance_info = credit_voucher_balance(
            user,
            locked.amount,
            reference_id=order_id,
            service_code="voucher_purchase",
            description="Voucher purchase",
        )
    if order_amount is not None:
        from decimal import Decimal as _Dec
        from portal.services.billing_document_service import schedule_voucher_purchase_billing

        schedule_voucher_purchase_billing(user=user, order_id=order_id, amount=_Dec(str(order_amount)))
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
    emit_notification_event(
        "payment_success",
        actor_id=user.id,
        payload={
            "user_id": user.id,
            "order_id": order_id,
            "amount": float(order.amount),
            "gateway": "cashfree",
        },
    )
    return issuance_info


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
                vi = get_parkpe_purchase_voucher_summary(
                    parkpe_reference_id=str(order_id),
                    parkpe_user_id=int(user.pk),
                )
                payload = {
                    "success": True,
                    "message": "Order already completed.",
                    "orderId": order_id,
                    "transactionId": order_id,
                    "gatewayPaymentId": completed.reference_id or "",
                    "amount": float(completed.amount),
                }
                if vi:
                    payload["voucherId"] = vi["voucher_id"]
                    payload["referenceNumber"] = vi["reference_number"]
                    payload["voucherCode"] = vi["voucher_code"]
                    payload["currency"] = vi["currency"]
                return Response(payload)
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
                            emit_notification_event(
                                "payment_failed",
                                actor_id=user.id,
                                payload={"user_id": user.id, "order_id": order_id, "reason": "terminal_status"},
                            )
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
                                emit_notification_event(
                                    "payment_failed",
                                    actor_id=user.id,
                                    payload={"user_id": user.id, "order_id": order_id, "reason": "all_failed"},
                                )
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
            emit_notification_event(
                "payment_pending_confirmation",
                actor_id=user.id,
                payload={"user_id": user.id, "order_id": order_id},
            )
            log_parkpe("parkpe_voucher", "Verify payment not confirmed", False, request, {"order_id": order_id})
            return Response(
                {"detail": "Payment not confirmed. Complete payment and try again."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            issuance = _complete_parkpe_payment_order(order, payment_id=payment_id, request=request)
            order.refresh_from_db()
            payload = {
                "success": True,
                "message": "Voucher issued successfully.",
                "orderId": order_id,
                "transactionId": order_id,
                "gatewayPaymentId": order.reference_id or (payment_id or ""),
                "amount": float(order.amount),
                "currency": "INR",
            }
            if issuance:
                payload["voucherId"] = issuance.get("voucher_id")
                payload["referenceNumber"] = issuance.get("reference_number")
                payload["voucherCode"] = issuance.get("voucher_code")
                if issuance.get("currency"):
                    payload["currency"] = issuance["currency"]
            return Response(payload)
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
                    "voucherCode": display_voucher_code_for_api(v.voucher_code),
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
        code = display_voucher_code_for_api(v.voucher_code)
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


def _parkpe_user_has_fleet_role(user) -> bool:
    rc = (getattr(user, "role_code", "") or "").strip().lower()
    return bool(rc.startswith("fleet_"))


@method_decorator(csrf_exempt, name="dispatch")
class FleetWorkspaceInterestStatusView(APIView):
    """GET /api/dashboard/fleet/interest/status — current user's fleet interest / access state."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            if _parkpe_user_has_fleet_role(user):
                return Response({"status": "approved"})
            latest = (
                FleetWorkspaceInterest.objects.filter(user=user).order_by("-created_at").first()
            )
            if not latest:
                return Response({"status": "none"})
            if latest.status == FleetWorkspaceInterest.STATUS_APPROVED:
                return Response(
                    {
                        "status": "approved",
                        "submittedAt": latest.created_at.isoformat() if latest.created_at else None,
                        "companyName": latest.company_name or "",
                        "message": latest.message or "",
                    }
                )
            body = {
                "status": latest.status,
                "submittedAt": latest.created_at.isoformat() if latest.created_at else None,
                "companyName": latest.company_name or "",
                "message": latest.message or "",
            }
            if latest.status == FleetWorkspaceInterest.STATUS_REJECTED:
                body["rejectionReason"] = latest.rejection_reason or ""
            return Response(body)
        except DatabaseError:
            logger.exception("fleet_interest_status_db")
            return Response(
                {
                    "detail": "Fleet interest tables are missing. On the server run: python manage.py migrate",
                    "status": "none",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


@method_decorator(csrf_exempt, name="dispatch")
class FleetWorkspaceInterestSubmitView(APIView):
    """POST /api/dashboard/fleet/interest — submit interest (consumer → admin review)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        user = request.user
        try:
            if _parkpe_user_has_fleet_role(user):
                return Response(
                    {"detail": "Fleet access is already enabled for this account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if FleetWorkspaceInterest.objects.filter(
                user=user, status=FleetWorkspaceInterest.STATUS_APPROVED
            ).exists():
                return Response(
                    {"detail": "Your fleet access request was already approved. Refresh the app or sign in again."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pending = FleetWorkspaceInterest.objects.filter(
                user=user, status=FleetWorkspaceInterest.STATUS_PENDING
            ).first()
            if pending:
                return Response(
                    {
                        "success": True,
                        "status": "pending",
                        "submittedAt": pending.created_at.isoformat() if pending.created_at else None,
                        "message": "Request already pending review.",
                    },
                    status=status.HTTP_200_OK,
                )
            data = request.data or {}
            company_name = (data.get("companyName") or data.get("company_name") or "").strip()[:200]
            message = (data.get("message") or "").strip()[:2000]
            row = FleetWorkspaceInterest.objects.create(
                user=user,
                status=FleetWorkspaceInterest.STATUS_PENDING,
                company_name=company_name,
                message=message,
            )
            log_parkpe(
                "parkpe_dashboard",
                "Fleet workspace interest submitted",
                True,
                request,
                {"interest_id": row.id},
            )
            return Response(
                {
                    "success": True,
                    "status": "pending",
                    "submittedAt": row.created_at.isoformat() if row.created_at else None,
                },
                status=status.HTTP_201_CREATED,
            )
        except DatabaseError:
            logger.exception("fleet_interest_submit_db")
            return Response(
                {
                    "detail": "Could not save your request. Run database migrations on the server: python manage.py migrate",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
