"""
General helper functions
"""
from typing import Any, Dict, List
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


def get_or_create_group(name: str, permissions: List[str] = None) -> Group:
    """
    Get or create Django group with permissions
    
    Args:
        name: Group name
        permissions: List of permission codenames (format: 'app_label.codename')
    
    Returns:
        Group instance
    """
    group, created = Group.objects.get_or_create(name=name)
    
    if permissions:
        for perm_codename in permissions:
            app_label, codename = perm_codename.split('.', 1)
            try:
                content_type = ContentType.objects.get(app_label=app_label)
                permission = Permission.objects.get(
                    content_type=content_type,
                    codename=codename
                )
                group.permissions.add(permission)
            except (ContentType.DoesNotExist, Permission.DoesNotExist):
                pass
    
    return group


def split_comma_separated(value: str) -> List[str]:
    """
    Split comma-separated string into list
    
    Args:
        value: Comma-separated string
    
    Returns:
        List of trimmed strings
    """
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]
