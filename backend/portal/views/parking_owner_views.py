"""
Parking Owner Hub Portal Views — Django template-based views.
Accessible to parking operators (owner/manager/attendant) via Hub login.
"""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, ListView
from datetime import timedelta, date
from decimal import Decimal

from portal.models import (
    ParkingLocation,
    ParkingSlot,
    ParkingZone,
    ParkingBooking,
    ParkingRevenue,
    ParkingOperator,
    ParkingTicket,
)
from portal.services.parking_service import get_owner_revenue_summary
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.views.parking_owner")

PARKING_LOGIN_URL = "/parking/login/"

_FEATURES = [
    ("📍", "Live Slot Map", "Real-time occupancy across all your locations"),
    ("📷", "QR Entry/Exit", "Scan customer QR codes for instant gate clearance"),
    ("💰", "Revenue Analytics", "Daily/monthly revenue, overstay charges, settlements"),
    ("🎫", "Booking Management", "View, filter and manage all bookings"),
]


def _require_parking_access(user, location_id=None):
    """Returns operator queryset for user, optionally filtered by location."""
    qs = ParkingOperator.objects.filter(user=user, is_active=True)
    if location_id:
        qs = qs.filter(location_id=location_id)
    return qs


class ParkingOperatorRequiredMixin(LoginRequiredMixin):
    """
    Mixin: user must be authenticated AND have at least one active ParkingOperator record.
    Unauthenticated users → /parking/login/
    Authenticated but no operator role → /parking/login/ with error message
    Staff users bypass the operator check.
    """
    login_url = PARKING_LOGIN_URL

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{PARKING_LOGIN_URL}?next={request.path}")
        if not request.user.is_staff:
            if not ParkingOperator.objects.filter(user=request.user, is_active=True).exists():
                messages.error(
                    request,
                    "You don't have parking operator access. "
                    "Contact your administrator to get assigned as an operator.",
                )
                return redirect(PARKING_LOGIN_URL)
        return super().dispatch(request, *args, **kwargs)


# ─── Parking Owner Login / Logout ─────────────────────────────────────────────

class ParkingOwnerLoginView(View):
    """
    Dedicated login page for parking operators.
    URL: /parking/login/
    POST: authenticate → verify ParkingOperator role → redirect to /parking/ (or ?next=)
    """
    template_name = "portal/parking/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            if ParkingOperator.objects.filter(user=request.user, is_active=True).exists() or request.user.is_staff:
                return redirect(request.GET.get("next") or "/parking/")
        return render(request, self.template_name, {
            "features": _FEATURES,
            "next": request.GET.get("next", "/parking/"),
        })

    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        next_url = request.POST.get("next", "/parking/")

        if not username or not password:
            return render(request, self.template_name, {
                "error": "Username and password are required.",
                "features": _FEATURES,
                "next": next_url,
            })

        user = authenticate(request, username=username, password=password)
        if not user:
            logger.warning("parking_login_failed", extra_data={"username": username})
            return render(request, self.template_name, {
                "error": "Invalid username or password.",
                "features": _FEATURES,
                "next": next_url,
            })

        if not user.is_active:
            return render(request, self.template_name, {
                "error": "Your account is inactive. Please contact support.",
                "features": _FEATURES,
                "next": next_url,
            })

        is_operator = ParkingOperator.objects.filter(user=user, is_active=True).exists()
        if not is_operator and not user.is_staff:
            return render(request, self.template_name, {
                "error": "You don't have parking operator access. "
                         "Contact your administrator to be assigned as a parking operator.",
                "features": _FEATURES,
                "next": next_url,
            })

        login(request, user)
        logger.info("parking_login_success", extra_data={"user_id": user.pk, "is_operator": is_operator})

        # Safe redirect — only allow relative paths
        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect("/parking/")


class ParkingOwnerLogoutView(View):
    """POST /parking/logout/ — logout and redirect to /parking/login/"""

    def post(self, request):
        logout(request)
        return redirect(PARKING_LOGIN_URL)

    def get(self, request):
        logout(request)
        return redirect(PARKING_LOGIN_URL)


# ─── Owner Dashboard ──────────────────────────────────────────────────────────

class ParkingOwnerDashboardView(ParkingOperatorRequiredMixin, TemplateView):
    """Main dashboard for parking operator — shows all managed locations."""

    template_name = "portal/parking/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()

        operators = _require_parking_access(self.request.user).select_related("location")
        location_data = []

        for op in operators:
            loc = op.location
            available_slots = ParkingSlot.objects.filter(
                zone__location=loc,
                status=ParkingSlot.STATUS_AVAILABLE,
                is_active=True,
            ).count()
            occupied_slots = ParkingSlot.objects.filter(
                zone__location=loc,
                status=ParkingSlot.STATUS_OCCUPIED,
                is_active=True,
            ).count()
            today_revenue = ParkingRevenue.objects.filter(
                location=loc, date=today
            ).aggregate(total=Sum("gross_revenue"))["total"] or Decimal("0")
            today_bookings = ParkingBooking.objects.filter(
                slot__zone__location=loc,
                created_at__date=today,
            ).count()
            active_sessions = ParkingBooking.objects.filter(
                slot__zone__location=loc,
                status=ParkingBooking.STATUS_ACTIVE,
            ).count()

            location_data.append({
                "location": loc,
                "role": op.role,
                "available_slots": available_slots,
                "occupied_slots": occupied_slots,
                "total_slots": loc.total_slots,
                "today_revenue": today_revenue,
                "today_bookings": today_bookings,
                "active_sessions": active_sessions,
                "occupancy_pct": (
                    int((occupied_slots / loc.total_slots) * 100) if loc.total_slots else 0
                ),
            })

        ctx["location_data"] = location_data
        ctx["today"] = today
        ctx["page_title"] = "Parking Dashboard"
        return ctx


# ─── Location Detail / Slot Map ───────────────────────────────────────────────

class ParkingLocationDetailView(ParkingOperatorRequiredMixin, TemplateView):
    """Live slot map for a specific parking location."""

    template_name = "portal/parking/location_detail.html"

    def dispatch(self, request, *args, **kwargs):
        self.location = get_object_or_404(ParkingLocation, pk=kwargs["location_id"])
        if not _require_parking_access(request.user, self.location.pk).exists():
            if not request.user.is_staff:
                return redirect("landing")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        zones = (
            ParkingZone.objects.filter(location=self.location, is_active=True)
            .prefetch_related("slots")
            .order_by("floor_level", "display_order")
        )
        zone_data = []
        for zone in zones:
            slots = list(zone.slots.filter(is_active=True).order_by("slot_code"))
            zone_data.append({
                "zone": zone,
                "slots": slots,
                "available": sum(1 for s in slots if s.status == "available"),
                "occupied": sum(1 for s in slots if s.status == "occupied"),
                "reserved": sum(1 for s in slots if s.status == "reserved"),
            })

        active_bookings = ParkingBooking.objects.filter(
            slot__zone__location=self.location,
            status=ParkingBooking.STATUS_ACTIVE,
        ).select_related("slot__zone", "customer")

        ctx.update({
            "location": self.location,
            "zone_data": zone_data,
            "active_bookings": active_bookings,
            "page_title": f"Live Map — {self.location.name}",
        })
        return ctx


# ─── Revenue Dashboard ────────────────────────────────────────────────────────

class ParkingRevenueView(ParkingOperatorRequiredMixin, TemplateView):
    """Revenue analytics dashboard for a parking location."""

    template_name = "portal/parking/revenue.html"

    def dispatch(self, request, *args, **kwargs):
        self.location = get_object_or_404(ParkingLocation, pk=kwargs["location_id"])
        if not _require_parking_access(request.user, self.location.pk).exists():
            if not request.user.is_staff:
                return redirect("landing")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days = int(self.request.GET.get("days", 30))
        summary = get_owner_revenue_summary(self.location.pk, days=days)

        # Last 7 days for mini chart
        recent_7 = summary["daily"][-7:] if len(summary["daily"]) >= 7 else summary["daily"]

        ctx.update({
            "location": self.location,
            "summary": summary,
            "recent_7": recent_7,
            "days": days,
            "page_title": f"Revenue — {self.location.name}",
        })
        return ctx


# ─── Bookings List ────────────────────────────────────────────────────────────

class ParkingBookingsListView(ParkingOperatorRequiredMixin, TemplateView):
    """All bookings for a location — with filters."""

    template_name = "portal/parking/bookings_list.html"

    def dispatch(self, request, *args, **kwargs):
        self.location = get_object_or_404(ParkingLocation, pk=kwargs["location_id"])
        if not _require_parking_access(request.user, self.location.pk).exists():
            if not request.user.is_staff:
                return redirect("landing")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        date_filter = self.request.GET.get("date", str(timezone.now().date()))
        status_filter = self.request.GET.get("status", "")

        qs = ParkingBooking.objects.filter(
            slot__zone__location=self.location
        ).select_related("slot__zone", "customer").order_by("-created_at")

        if date_filter:
            qs = qs.filter(created_at__date=date_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)

        ctx.update({
            "location": self.location,
            "bookings": qs[:200],
            "total": qs.count(),
            "date_filter": date_filter,
            "status_filter": status_filter,
            "status_choices": ParkingBooking.STATUS_CHOICES,
            "page_title": f"Bookings — {self.location.name}",
        })
        return ctx


# ─── Attendant QR Verify (AJAX) ───────────────────────────────────────────────

class ParkingVerifyEntryView(ParkingOperatorRequiredMixin, TemplateView):
    """Page for attendant to scan QR and process entry."""

    template_name = "portal/parking/verify_entry.html"

    def post(self, request, location_id):
        from portal.services.parking_service import process_entry
        from portal.services.parking_notification_service import send_exit_receipt_whatsapp

        action = request.POST.get("action", "entry")
        booking_ref = request.POST.get("booking_ref", "").strip()
        qr_payload = request.POST.get("qr_payload", "").strip() or None

        if not booking_ref:
            return JsonResponse({"success": False, "error": "Booking reference required."})

        try:
            if action == "entry":
                booking = process_entry(
                    booking_reference=booking_ref,
                    qr_payload=qr_payload,
                    attendant=request.user,
                )
                return JsonResponse({
                    "success": True,
                    "message": f"Entry recorded. Slot: {booking.slot_code}",
                    "booking_reference": booking_ref,
                    "entry_time": booking.actual_entry_time.strftime("%d %b %Y, %I:%M %p"),
                    "vehicle_number": booking.vehicle_number,
                })
            elif action == "exit":
                from portal.services.parking_service import process_exit
                summary = process_exit(booking_reference=booking_ref, attendant=request.user)
                try:
                    from portal.models import ParkingBooking
                    b = ParkingBooking.objects.get(booking_reference=booking_ref)
                    send_exit_receipt_whatsapp(b)
                except Exception:
                    pass
                return JsonResponse({"success": True, **summary})
        except ValueError as e:
            return JsonResponse({"success": False, "error": str(e)})
        except Exception as e:
            logger.exception("parking_verify_entry_error", extra_data={"error": str(e)})
            return JsonResponse({"success": False, "error": "Server error. Try again."})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["location"] = get_object_or_404(ParkingLocation, pk=self.kwargs["location_id"])
        ctx["page_title"] = "Entry / Exit Verification"
        return ctx
