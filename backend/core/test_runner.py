"""
Custom test runner to handle allauth migration issues
"""
from django.test.runner import DiscoverRunner
from django.core.management import call_command
from django.db import connection


class CustomTestRunner(DiscoverRunner):
    """Custom test runner that fakes problematic allauth migrations"""
    
    def setup_databases(self, **kwargs):
        """Override to fake problematic migrations"""
        # Call parent to create test database
        old_config = super().setup_databases(**kwargs)
        
        # Fake the problematic allauth migration after database is created
        try:
            db_name = connection.settings_dict['NAME']
            if 'test' in db_name.lower():
                # Fake the migration if not already applied
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM django_migrations 
                            WHERE app = 'account' AND name = '0006_emailaddress_lower'
                        """)
                        count = cursor.fetchone()[0]
                        if count == 0:
                            # Fake the migration
                            call_command('migrate', 'account', '0006', '--fake', verbosity=0)
                except:
                    # Try to fake anyway
                    try:
                        call_command('migrate', 'account', '0006', '--fake', verbosity=0)
                    except:
                        pass
        except:
            pass
        
        return old_config
