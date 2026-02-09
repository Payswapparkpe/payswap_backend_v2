"""
Partner Vendor Service - manages which vendors a partner can use per service.
Admin assigns vendors; API requests are routed to the assigned vendor.
"""
import logging
from portal.models import ResellerPartner, ApiVendor, PartnerVendorAssignment

logger = logging.getLogger(__name__)


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
        """
        assignment = (
            PartnerVendorAssignment.objects.filter(
                partner=partner,
                service_code=service_code,
                is_active=True,
                is_primary=True,
            )
            .select_related('vendor')
            .first()
        )
        return assignment.vendor if assignment else None

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
