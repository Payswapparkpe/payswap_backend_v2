"""
Portal app configuration
"""
from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'portal'
    verbose_name = 'Portal'
    
    def ready(self):
        """Import signals when app is ready"""
        import portal.signals  # noqa
