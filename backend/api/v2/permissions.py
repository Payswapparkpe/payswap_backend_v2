"""
API Version 2 Permissions - External Parties
"""
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from api.exceptions import AdminDisabledException
from portal.models import ApiVendor, VendorApi
from portal.services.partner_vendor_service import PartnerVendorService
from portal.services.api_registry import SERVICE_ACTION_TO_API_CODES


class IsExternalUser(permissions.BasePermission):
    """
    Permission class for external API access.
    Allows access to:
    - Public endpoints (no auth required)
    - API key authenticated users
    - Token authenticated users (for partners)
    """
    
    def has_permission(self, request, view):
        # Public access by default
        # Override in views that require authentication
        return True


class HasAPIKey(permissions.BasePermission):
    """
    Permission for API key authentication (for external partners)
    Requires valid API key in request
    """
    
    def has_permission(self, request, view):
        # Check if API key is attached to request (from authentication)
        if hasattr(request, 'api_key') and request.api_key:
            return True
        return False


class HasServicePermission(permissions.BasePermission):
    """
    Permission class that checks service-level permissions
    Usage: permission_classes = [HasAPIKey, HasServicePermission]
    """
    
    # Override in view: service_name = 'voucher', required_action = 'issue'
    service_name = None
    required_action = None
    
    def has_permission(self, request, view):
        # Must have API key first
        if not hasattr(request, 'api_key') or not request.api_key:
            return False
        
        api_key = request.api_key
        
        # Get service and action from view
        service = getattr(view, 'service_name', None) or self.service_name
        action = getattr(view, 'required_action', None) or self.required_action
        
        if not service or not action:
            # If not specified, allow (view should handle validation)
            return True
        
        # Check permission
        has_perm = api_key.has_permission(service, action)
        
        if not has_perm:
            raise PermissionDenied(
                f'API key does not have permission for {service}.{action}'
            )

        # Admin toggles enforcement (vendor/API OFF => AD400)
        partner = api_key.partner
        vendor = PartnerVendorService.get_partner_vendor(partner, service)
        if not vendor or not vendor.is_active:
            raise AdminDisabledException(
                detail=f"Service '{service}' is disabled by admin for this partner."
            )

        api_codes = SERVICE_ACTION_TO_API_CODES.get(service, {}).get(action, [])
        if api_codes:
            active_api_exists = VendorApi.objects.filter(
                vendor=vendor,
                api_code__in=api_codes,
                is_active=True,
            ).exists()
            if not active_api_exists:
                raise AdminDisabledException(
                    detail=f"API for '{service}.{action}' is disabled by admin."
                )
        
        return True


class HasAPIKeyOrAuthenticated(permissions.BasePermission):
    """
    Allow access if request has valid API key (v2 partner) or authenticated user (JWT/session).
    Used for endpoints that serve both partner API and internal/admin clients.
    """

    def has_permission(self, request, view):
        if getattr(request, "api_key", None):
            return True
        return request.user and request.user.is_authenticated


class HasVendorAccess(permissions.BasePermission):
    """
    Check if partner has access to the vendor being requested.
    If request specifies vendor (query or body), validates partner is assigned that vendor.
    If no vendor specified, allow (view will use partner's primary via VendorRouter).
    """

    def has_permission(self, request, view):
        if not getattr(request, "api_key", None) or not request.api_key:
            return False
        partner = request.api_key.partner
        service_code = getattr(view, "service_name", None)
        if not service_code:
            return True
        vendor_code = None
        if request.method == "GET":
            vendor_code = (request.query_params.get("vendor") or "").strip().lower() or None
        else:
            vendor_code = (request.data.get("vendor") if getattr(request, "data", None) else None) or None
            if isinstance(vendor_code, str):
                vendor_code = vendor_code.strip().lower() or None
        if not vendor_code:
            return True
        try:
            vendor = ApiVendor.objects.get(code=vendor_code, is_active=True)
        except ApiVendor.DoesNotExist:
            raise AdminDisabledException(
                detail=f"Vendor '{vendor_code}' is disabled by admin or unavailable."
            )
        return PartnerVendorService.can_partner_use_vendor(partner, service_code, vendor)
