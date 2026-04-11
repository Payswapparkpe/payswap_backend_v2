"""
Django signals for portal app
Handles automatic synchronization between Roles, Groups, and Users
"""
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import Group
from portal.models import User, Role
from portal.utils.role_utils import sync_user_to_groups, sync_role_permissions_to_group


@receiver(post_save, sender=User)
def sync_user_to_groups_on_save(sender, instance, created, **kwargs):
    """
    Automatically sync user to Django Groups when user is created or role is changed
    """
    if instance.role:
        sync_user_to_groups(instance, instance.role)


@receiver(post_save, sender=Role)
def sync_role_permissions_to_group_on_save(sender, instance, created, **kwargs):
    """
    Automatically sync Role.default_permissions to Django Group permissions
    """
    sync_role_permissions_to_group(instance)


@receiver(m2m_changed, sender=Role.default_permissions.through)
def sync_role_permissions_to_group_on_m2m_change(sender, instance, action, **kwargs):
    """
    Sync Role.default_permissions to Django Group when permissions are added/removed
    """
    if action in ('post_add', 'post_remove', 'post_clear'):
        sync_role_permissions_to_group(instance)
