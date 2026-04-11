"""
Custom template tags for portal app
"""
from urllib.parse import urlparse

from django import template
from django.urls import reverse, NoReverseMatch
from portal.utils.permission_utils import user_has_permission, user_has_hub_permission

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


@register.filter
def has_hub_permission(user, permission_codename):
    """
    Check Hub RBAC permission through role assignments.
    """
    if not user or not user.is_authenticated:
        return False
    return user_has_hub_permission(user, permission_codename)


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


@register.simple_tag(takes_context=True)
def smart_back_url(context, fallback_name='dashboard'):
    """
    Return safest backward URL using next/referrer/fallback.
    """
    request = context.get('request')
    if not request:
        return '/'

    next_url = (
        (request.GET.get('next') or '').strip()
        or (request.POST.get('next') or '').strip()
    )
    if next_url.startswith('/') and not next_url.startswith('//'):
        return next_url

    referrer = (request.META.get('HTTP_REFERER') or '').strip()
    if referrer:
        parsed = urlparse(referrer)
        host = (parsed.netloc or '').strip().lower()
        if not host or host == request.get_host().lower():
            path = parsed.path or '/'
            if parsed.query:
                path = f"{path}?{parsed.query}"
            if path != request.get_full_path():
                return path

    try:
        return reverse(fallback_name)
    except NoReverseMatch:
        return '/dashboard/'
