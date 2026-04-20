"""
Partner Vendor Service - manages which vendors a partner can use per service.
Admin assigns vendors; API requests are routed to the assigned vendor.

Step 3: get_partner_vendor is cached in Redis (TTL 120s) to reduce DB load at v2 scale.
Cache is invalidated on assign_vendor_to_partner and unassign_vendor.
"""
import logging
from django.core.cache import cache

from portal.models import ResellerPartner, ApiVendor, PartnerVendorAssignment

logger = logging.getLogger(__name__)

# Cache TTL for partner→vendor lookup (Step 3: 1M-user scale)
PARTNER_VENDOR_CACHE_TTL = 120
PARTNER_VENDOR_CACHE_KEY_PREFIX = "partner_vendor:"
# Sentinel: cached when partner has no primary vendor for service (avoids repeated DB misses)
PARTNER_VENDOR_CACHE_NONE = 0


def _partner_vendor_cache_key(partner_id, service_code):
    return f"{PARTNER_VENDOR_CACHE_KEY_PREFIX}{partner_id}:{service_code}"


def _invalidate_partner_vendor_cache(partner_id, service_code):
    try:
        cache.delete(_partner_vendor_cache_key(partner_id, service_code))
    except Exception as e:
        logger.warning("Failed to invalidate partner_vendor cache: %s", e)


class PartnerVendorService:
    """Service for partner-vendor assignment and lookup."""

    @staticmethod
    def assign_vendor_to_partner(partner, service_code, vendor, is_primary=True, priority=1, assigned_by=None):
        """
        Assign a vendor to a partner for a specific service.
        If is_primary=True, any existing primary for this partner+service is unset.
        """
        if is_primary:
            PartnerVendorAssignment.objects.filter(
                partner=partner,
                service_code=service_code,
                is_primary=True,
                is_active=True,
            ).update(is_primary=False)
        assignment, created = PartnerVendorAssignment.objects.update_or_create(
            partner=partner,
            service_code=service_code,
            vendor=vendor,
            defaults={
                'is_primary': is_primary,
                'is_active': True,
                'priority': priority,
                'assigned_by': assigned_by,
            },
        )
        _invalidate_partner_vendor_cache(partner.id, service_code)
        if created:
            logger.info(
                'Assigned vendor %s to partner %s for service %s',
                vendor.code, partner.partner_code, service_code,
            )
        return assignment

    @staticmethod
    def unassign_vendor(partner, service_code, vendor):
        """Deactivate (soft) or delete assignment."""
        updated = PartnerVendorAssignment.objects.filter(
            partner=partner,
            service_code=service_code,
            vendor=vendor,
        ).update(is_active=False)
        _invalidate_partner_vendor_cache(partner.id, service_code)
        if updated:
            logger.info(
                'Unassigned vendor %s from partner %s for service %s',
                vendor.code, partner.partner_code, service_code,
            )
        return updated

    @staticmethod
    def get_partner_vendor(partner, service_code):
        """
        Get the primary vendor for a partner's service.
        Returns ApiVendor or None if no assignment.
        Cached in Redis (Step 3) to reduce DB load on v2 requests.
        """
        cache_key = _partner_vendor_cache_key(partner.id, service_code)
        cached = cache.get(cache_key)
        if cached is not None:
            if cached == PARTNER_VENDOR_CACHE_NONE:
                return None
            try:
                vendor = ApiVendor.objects.get(pk=cached)
                if not vendor.is_active:
                    cache.delete(cache_key)
                    return None
                return vendor
            except ApiVendor.DoesNotExist:
                cache.delete(cache_key)
        assignment = (
            PartnerVendorAssignment.objects.filter(
                partner=partner,
                service_code=service_code,
                is_active=True,
                is_primary=True,
                vendor__is_active=True,
            )
            .select_related('vendor')
            .first()
        )
        vendor = assignment.vendor if assignment else None
        cache.set(
            cache_key,
            vendor.pk if vendor else PARTNER_VENDOR_CACHE_NONE,
            timeout=PARTNER_VENDOR_CACHE_TTL,
        )
        return vendor

    @staticmethod
    def get_partner_allowed_vendors(partner, service_code):
        """Get all allowed vendors for a service, ordered by priority."""
        return list(
            PartnerVendorAssignment.objects.filter(
                partner=partner,
                service_code=service_code,
                is_active=True,
            )
            .select_related('vendor')
            .order_by('priority', '-is_primary')
        )

    @staticmethod
    def can_partner_use_vendor(partner, service_code, vendor):
        """Check if partner can use a specific vendor for the service."""
        return PartnerVendorAssignment.objects.filter(
            partner=partner,
            service_code=service_code,
            vendor=vendor,
            is_active=True,
        ).exists()

    @staticmethod
    def get_assignments_for_partner(partner):
        """Get all vendor assignments for a partner, grouped by service_code."""
        from collections import defaultdict
        assignments = (
            PartnerVendorAssignment.objects.filter(partner=partner, is_active=True)
            .select_related('vendor')
            .order_by('service_code', 'priority', '-is_primary')
        )
        by_service = defaultdict(list)
        for a in assignments:
            by_service[a.service_code].append(a)
        return dict(by_service)

    @staticmethod
    def execute_with_failover(partner, service_code, fn, is_success=None):
        """
        Call fn(vendor) for each allowed vendor in priority order; on failure try next.
        fn(vendor) should return a result (e.g. dict with 'success' key) or raise.
        is_success(result) can be provided; default: result is truthy and result.get('success') is True.
        Returns (result, vendor_used). If all fail, returns last result and last vendor (or raises if fn raised).
        """
        assignments = PartnerVendorService.get_partner_allowed_vendors(partner, service_code)
        if not assignments:
            return None, None
        if is_success is None:
            def is_success(r):
                if r is None:
                    return False
                if isinstance(r, dict):
                    return r.get('success') is True
                return bool(r)
        last_result = None
        last_vendor = None
        for assignment in assignments:
            vendor = assignment.vendor
            try:
                result = fn(vendor)
                last_result = result
                last_vendor = vendor
                if is_success(result):
                    return result, vendor
            except Exception:
                last_result = {'success': False, 'message': 'Vendor call failed', 'vendor': vendor.code}
                last_vendor = vendor
                logger.warning(
                    'Vendor failover: %s failed for partner %s service %s, trying next',
                    vendor.code, partner.partner_code, service_code,
                )
        return last_result, last_vendor
