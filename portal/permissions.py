"""
Custom permission classes for portal app
"""
from rest_framework import permissions
from portal.utils.permission_utils import user_has_permission, user_has_any_permission, user_has_all_permissions
from portal.utils.user_utils import is_mfa_required_role


class HasPermission(permissions.BasePermission):
    """
    Check if user has specific permission
    Usage: permission_classes = [HasPermission('portal.view_user')]
    """
    
    def __init__(self, permission_codename: str, app_label: str = 'portal'):
        self.permission_codename = permission_codename
        self.app_label = app_label
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return user_has_permission(request.user, self.permission_codename, self.app_label)


class HasAnyPermission(permissions.BasePermission):
    """
    Check if user has any of the specified permissions
    Usage: permission_classes = [HasAnyPermission(['portal.view_user', 'portal.add_user'])]
    """
    
    def __init__(self, permission_codenames: list, app_label: str = 'portal'):
        self.permission_codenames = permission_codenames
        self.app_label = app_label
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return user_has_any_permission(request.user, self.permission_codenames, self.app_label)


class HasAllPermissions(permissions.BasePermission):
    """
    Check if user has all specified permissions
    Usage: permission_classes = [HasAllPermissions(['portal.view_user', 'portal.add_user'])]
    """
    
    def __init__(self, permission_codenames: list, app_label: str = 'portal'):
        self.permission_codenames = permission_codenames
        self.app_label = app_label
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return user_has_all_permissions(request.user, self.permission_codenames, self.app_label)


class IsRole(permissions.BasePermission):
    """
    Check if user has specific role
    Usage: permission_classes = [IsRole('admin')]
    """
    
    def __init__(self, role_code: str):
        self.role_code = role_code
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'role_code'):
            return request.user.role_code.lower() == self.role_code.lower()
        return False


class IsRoleOrHigher(permissions.BasePermission):
    """
    Check if user has role or higher hierarchy
    Usage: permission_classes = [IsRoleOrHigher('employee')]
    """
    
    def __init__(self, role_code: str):
        self.role_code = role_code
    
    def __call__(self):
        """Make the instance callable for drf_spectacular compatibility"""
        return self
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'role') and request.user.role:
            user_level = request.user.role.hierarchy_level
            # Get required role level
            from portal.models import Role
            try:
                required_role = Role.objects.get(code=self.role_code)
                return user_level >= required_role.hierarchy_level
            except Role.DoesNotExist:
                return False
        return False


class CanCreateUser(permissions.BasePermission):
    """
    Check if user can create other users
    Only Admin, Super, and higher hierarchy can create users
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'role') and request.user.role:
            # Admin and Super can create users
            allowed_roles = ['admin', 'super']
            return request.user.role_code.lower() in allowed_roles
        return False


class CanManageKYC(permissions.BasePermission):
    """
    Check if user can manage KYC
    Admin and Super can verify KYC
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'role_code'):
            allowed_roles = ['admin', 'super', 'employee']
            return request.user.role_code.lower() in allowed_roles
        return False


class CanManagePermissions(permissions.BasePermission):
    """
    Check if user can manage permissions
    Only Admin can manage permissions
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'role_code'):
            return request.user.role_code.lower() == 'admin'
        return False


# ============================================================================
# VOUCHERX PERMISSIONS
# ============================================================================

class CanAccessVoucherX(permissions.BasePermission):
    """
    Check if user can access VoucherX
    Default: Admin and Super users
    Override: Users with 'portal.view_voucherx' permission
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check permission override first
        if user_has_permission(request.user, 'view_voucherx', 'portal'):
            return True
        
        # Default role-based access
        if hasattr(request.user, 'role_code'):
            allowed_roles = ['admin', 'super']
            if request.user.role_code.lower() in allowed_roles or request.user.is_staff:
                return True
        
        return False


class CanManageVoucherXBrands(permissions.BasePermission):
    """
    Check if user can manage VoucherX brands (create, onboard)
    Default: Admin and Super users
    Override: Users with 'portal.manage_voucherx_brands' permission
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check permission override first
        if user_has_permission(request.user, 'manage_voucherx_brands', 'portal'):
            return True
        
        # Default role-based access
        if hasattr(request.user, 'role_code'):
            allowed_roles = ['admin', 'super']
            if request.user.role_code.lower() in allowed_roles or request.user.is_staff:
                return True
        
        return False


class CanIssueVouchers(permissions.BasePermission):
    """
    Check if user can issue vouchers
    Default: Admin, Super, and Employee users
    Override: Users with 'portal.issue_vouchers' permission
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check permission override first
        if user_has_permission(request.user, 'issue_vouchers', 'portal'):
            return True
        
        # Default role-based access
        if hasattr(request.user, 'role_code'):
            allowed_roles = ['admin', 'super', 'employee']
            if request.user.role_code.lower() in allowed_roles or request.user.is_staff:
                return True
        
        return False


class CanReviewBrandOnboarding(permissions.BasePermission):
    """
    Check if user can review brand onboarding
    Default: Admin and Super users
    Override: Users with 'portal.review_brand_onboarding' permission
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check permission override first
        if user_has_permission(request.user, 'review_brand_onboarding', 'portal'):
            return True
        
        # Default role-based access
        if hasattr(request.user, 'role_code'):
            allowed_roles = ['admin', 'super']
            if request.user.role_code.lower() in allowed_roles or request.user.is_staff:
                return True
        
        return False
