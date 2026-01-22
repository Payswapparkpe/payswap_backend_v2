"""
Custom template tags for portal app
"""
from django import template
from portal.utils.permission_utils import user_has_permission

register = template.Library()


@register.filter
def has_permission(user, permission_codename):
    """
    Check if user has permission
    
    Usage: {% if user|has_permission:'portal.view_user' %}
    """
    if not user or not user.is_authenticated:
        return False
    return user_has_permission(user, permission_codename)


@register.simple_tag
def get_user_role_display(user):
    """
    Get user role display name
    
    Usage: {% get_user_role_display user %}
    """
    if user and hasattr(user, 'role'):
        return user.role.name if user.role else 'No Role'
    return 'No Role'


@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary by key
    
    Usage: {{ dictionary|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
