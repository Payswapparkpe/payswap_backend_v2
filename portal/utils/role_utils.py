"""
Role and Group management utilities
Handles synchronization between Role model and Django Groups
"""
from typing import List, Optional
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from portal.models import User, Role
from portal.utils.helpers import get_or_create_group


def get_role_group(role: Role) -> Optional[Group]:
    """
    Get Django Group associated with a Role
    
    Args:
        role: Role instance
    
    Returns:
        Group instance or None
    """
    if not role:
        return None
    
    group_name = f"{role.name} Group"
    try:
        return Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return None


def sync_role_permissions_to_group(role: Role) -> Group:
    """
    Sync Role.default_permissions to Django Group permissions
    
    Args:
        role: Role instance
    
    Returns:
        Group instance
    """
    if not role:
        return None
    
    # Get or create group for this role
    group_name = f"{role.name} Group"
    group = get_or_create_group(group_name)
    
    # Sync permissions from Role.default_permissions to Group
    with transaction.atomic():
        # Clear existing permissions
        group.permissions.clear()
        
        # Add permissions from Role.default_permissions
        if role.default_permissions.exists():
            group.permissions.set(role.default_permissions.all())
    
    return group


def sync_user_to_groups(user: User, role: Optional[Role] = None) -> None:
    """
    Sync user to appropriate Django Groups based on role
    
    Args:
        user: User instance
        role: Optional Role instance (if None, uses user.role)
    """
    if not user:
        return
    
    role = role or user.role
    if not role:
        return
    
    # Get the group for this role
    group = get_role_group(role)
    if not group:
        # Create group if it doesn't exist
        group = sync_role_permissions_to_group(role)
    
    # Remove user from all role groups first
    role_groups = Group.objects.filter(name__endswith=' Group')
    for role_group in role_groups:
        user.groups.remove(role_group)
    
    # Add user to the appropriate group
    if group:
        user.groups.add(group)


def assign_role_to_user(user: User, role: Role) -> None:
    """
    Assign role to user and sync to groups
    
    Args:
        user: User instance
        role: Role instance
    """
    with transaction.atomic():
        user.role = role
        user.role_code = role.code
        user.save()
        sync_user_to_groups(user, role)


def change_user_role(user: User, new_role_code: str) -> None:
    """
    Change user's role
    
    Args:
        user: User instance
        new_role_code: New role code
    """
    try:
        new_role = Role.objects.get(code=new_role_code)
        assign_role_to_user(user, new_role)
    except Role.DoesNotExist:
        raise ValueError(f"Role with code '{new_role_code}' does not exist")


def assign_permission_to_user(user: User, permission: Permission) -> None:
    """
    Assign permission directly to user (not via group)
    
    Args:
        user: User instance
        permission: Permission instance
    """
    user.user_permissions.add(permission)


def revoke_permission_from_user(user: User, permission: Permission) -> None:
    """
    Revoke permission from user
    
    Args:
        user: User instance
        permission: Permission instance
    """
    user.user_permissions.remove(permission)


def assign_permission_to_role(role: Role, permission: Permission) -> None:
    """
    Assign permission to role (adds to default_permissions and syncs to group)
    
    Args:
        role: Role instance
        permission: Permission instance
    """
    with transaction.atomic():
        role.default_permissions.add(permission)
        sync_role_permissions_to_group(role)
        
        # Update all users with this role
        for user in role.users.all():
            sync_user_to_groups(user, role)


def revoke_permission_from_role(role: Role, permission: Permission) -> None:
    """
    Revoke permission from role (removes from default_permissions and syncs to group)
    
    Args:
        role: Role instance
        permission: Permission instance
    """
    with transaction.atomic():
        role.default_permissions.remove(permission)
        sync_role_permissions_to_group(role)
        
        # Update all users with this role
        for user in role.users.all():
            sync_user_to_groups(user, role)


def get_user_permissions(user: User) -> List[Permission]:
    """
    Get all permissions for user (from groups + direct permissions)
    
    Args:
        user: User instance
    
    Returns:
        List of Permission instances
    """
    # Get permissions from groups
    group_permissions = Permission.objects.filter(group__user=user)
    
    # Get direct user permissions
    user_permissions = user.user_permissions.all()
    
    # Combine and return unique permissions
    all_permissions = set(group_permissions) | set(user_permissions)
    return list(all_permissions)


def user_has_permission_via_role(user: User, permission_codename: str, app_label: str = 'portal') -> bool:
    """
    Check if user has permission via their role
    
    Args:
        user: User instance
        permission_codename: Permission codename
        app_label: App label
    
    Returns:
        True if user has permission via role
    """
    if not user or not user.role:
        return False
    
    return user.role.default_permissions.filter(
        content_type__app_label=app_label,
        codename=permission_codename
    ).exists()
