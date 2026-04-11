"""
API Version 1 Views - Internal Access
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from .permissions import IsInternalUser, IsStaffOnly
from api.mixins.response_mixin import StandardResponseMixin
from api.mixins.logging_mixin import APILoggingMixin


class HealthCheckView(APILoggingMixin, StandardResponseMixin, APIView):
    """
    Health check endpoint for API v1 (Internal)
    """
    permission_classes = [IsInternalUser]

    def get(self, request):
        return self.success_response(
            message="API is healthy",
            data={
                "version": "v1",
                "access_type": "internal",
                "user": request.user.username if request.user.is_authenticated else None,
            },
            request=request
        )


class RuntimeConfigView(StandardResponseMixin, APIView):
    """
    Dynamic API config for frontend (Parkpe / Payswap Angular).
    Returns empty apis list – internal apps; endpoints are fixed in frontend.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        app = request.query_params.get("app", "parkpe").strip().lower()
        return self.success_response(
            message="Runtime config",
            data={"app": app, "apis": []},
            request=request,
        )


class ControlOverviewView(StandardResponseMixin, APIView):
    """
    Control tower overview – technical, financial, operational summary.
    Staff only.
    """
    permission_classes = [IsAuthenticated, IsStaffOnly]

    def get(self, request):
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        technical = {}
        financial = {}
        operational = {}
        business = {}

        try:
            from portal.models import APIKeyUsageLog
            usage_q = APIKeyUsageLog.objects.filter(created_at__gte=last_24h)
            technical["api_key_usage_24h_total"] = usage_q.count()
            technical["api_key_usage_24h_errors"] = usage_q.filter(status_code__gte=400).count()
        except Exception:
            technical["api_key_usage_24h_total"] = 0
            technical["api_key_usage_24h_errors"] = 0

        try:
            from portal.models import ResellerPartnerTransaction, ResellerPartnerSettlement
            txn_q = ResellerPartnerTransaction.objects.filter(created_at__gte=last_7d, status="COMPLETED")
            rev = txn_q.filter(transaction_type="REVENUE").aggregate(s=Sum("amount"))["s"]
            comm = txn_q.filter(transaction_type="COMMISSION").aggregate(s=Sum("commission_amount"))["s"]
            financial["revenue_7d"] = str(rev) if rev is not None else "0"
            financial["commission_7d"] = str(comm) if comm is not None else "0"
            pending = ResellerPartnerSettlement.objects.filter(status="PENDING").aggregate(s=Sum("settlement_amount"))["s"]
            financial["pending_settlements_total"] = str(pending) if pending is not None else "0"
        except Exception:
            financial["revenue_7d"] = "0"
            financial["commission_7d"] = "0"
            financial["pending_settlements_total"] = "0"

        try:
            from portal.models import ResellerPartner
            operational["partners_active"] = ResellerPartner.objects.filter(status="ACTIVE").count()
        except Exception:
            operational["partners_active"] = 0

        try:
            from portal.models import APIKeyUsageLog as UsageLog
            business["distinct_partners_24h"] = (
                UsageLog.objects.filter(created_at__gte=last_24h)
                .values("partner")
                .distinct()
                .count()
            )
        except Exception:
            business["distinct_partners_24h"] = 0

        return self.success_response(
            message="Control tower overview",
            data={
                "technical": technical,
                "financial": financial,
                "operational": operational,
                "business": business,
            },
            request=request,
        )


class ControlAPIsListView(StandardResponseMixin, APIView):
    """GET /api/v1/control/apis/ – list APIs. Returns empty (api_management removed)."""
    permission_classes = [IsAuthenticated, IsStaffOnly]

    def get(self, request):
        return self.success_response(message="API list", data={"apis": []}, request=request)


class ControlPartnersListView(StandardResponseMixin, APIView):
    """GET /api/v1/control/partners/ – list partners. Staff only."""
    permission_classes = [IsAuthenticated, IsStaffOnly]

    def get(self, request):
        from portal.models import ResellerPartner
        partners = [
            {
                "id": p.id,
                "partner_code": p.partner_code,
                "company_name": p.company_name,
            }
            for p in ResellerPartner.objects.filter(status="ACTIVE").order_by("partner_code")
        ]
        return self.success_response(message="Partners list", data={"partners": partners}, request=request)
