"""
Portal app configuration
"""
from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'portal'
    verbose_name = 'Portal'
    
    def ready(self):
        """Import signals and register service flow handlers when app is ready."""
        import portal.signals  # noqa
        try:
            from portal.services.handler_registry import register_default_handlers
            register_default_handlers()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Could not register default flow handlers: %s", e)
