"""
Management command to fix ticket migration index conflicts
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Drop conflicting indexes from ticket management migration'

    def handle(self, *args, **options):
        """Drop conflicting indexes if they exist"""
        with connection.cursor() as cursor:
            # List of indexes that might conflict
            indexes_to_drop = [
                'portal_tick_ticket__idx',
                'portal_tick_assigne_idx',
            ]
            
            dropped_count = 0
            for index_name in indexes_to_drop:
                try:
                    # Check if index exists
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT 1 FROM pg_indexes 
                            WHERE indexname = %s
                        );
                    """, [index_name])
                    
                    exists = cursor.fetchone()[0]
                    
                    if exists:
                        cursor.execute(f'DROP INDEX IF EXISTS {index_name};')
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Dropped index: {index_name}')
                        )
                        dropped_count += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'⊘ Index does not exist: {index_name}')
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Error dropping {index_name}: {str(e)}')
                    )
            
            if dropped_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ Successfully dropped {dropped_count} conflicting index(es).'
                    )
                    + '\nYou can now run: python manage.py migrate portal'
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('\n✓ No conflicting indexes found.')
                )
