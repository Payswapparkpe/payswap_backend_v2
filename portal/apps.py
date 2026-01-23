"""
Portal app configuration
"""
from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'portal'
    verbose_name = 'Portal'
    
    def ready(self):
        """Import signals and override createsuperuser command when app is ready"""
        import portal.signals  # noqa
        
        # Override Django's default createsuperuser command
        # This must be done in ready() after Django's command registry is initialized
        try:
            from django.core.management import _commands
            # Force our custom command to override Django's default
            _commands['createsuperuser'] = 'portal.management.commands.createsuperuser'
        except (ImportError, AttributeError, KeyError):
            # If override fails, continue - command will be discovered normally
            pass
