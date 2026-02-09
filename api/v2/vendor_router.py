"""
Vendor Router – routes API requests to the partner's assigned vendor per service.
Admin assigns vendors to partners; this module resolves which vendor to use for a request.
"""
from rest_framework.exceptions import PermissionDenied

from portal.models import ApiVendor
from portal.services.partner_vendor_service import PartnerVendorService


class VendorRouter:
    """Resolves which vendor a partner can use for a given service."""

    @staticmethod
    def get_vendor_for_request(request, service_code):
        """
        Determine which vendor to use for this request based on partner's assignment.
        Requires request.api_key and request.api_key.partner (set by APIKeyAuthentication).
        Returns ApiVendor instance.
        Raises PermissionDenied if no API key or no vendor assigned.
        """
        if not getattr(request, "api_key", None) or not request.api_key:
            raise PermissionDenied("API key required")
        partner = request.api_key.partner
        vendor = PartnerVendorService.get_partner_vendor(partner, service_code)
        if not vendor:
            raise PermissionDenied(
                f"No vendor assigned for service '{service_code}'. Contact admin to assign a vendor."
            )
        return vendor

    @staticmethod
    def get_vendor_code_for_request(request, service_code):
        """
        Convenience: return vendor code string for the partner's assigned vendor.
        Returns None if no assignment.
        """
        try:
            vendor = VendorRouter.get_vendor_for_request(request, service_code)
            return vendor.code if vendor else None
        except PermissionDenied:
            raise
