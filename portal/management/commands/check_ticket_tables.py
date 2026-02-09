"""
Management command to check ticket management tables and indexes
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Check ticket management tables and indexes status'

    def handle(self, *args, **options):
        """Check what tables and indexes exist"""
        with connection.cursor() as cursor:
            # Check tables
            self.stdout.write(self.style.SUCCESS('\n=== Ticket Management Tables ===\n'))
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'portal_%'
                AND table_name IN (
                    'portal_department',
                    'portal_agent',
                    'portal_ticket',
                    'portal_ticket_note',
                    'portal_ticket_attachment',
                    'portal_ticket_assignment_history'
                )
                ORDER BY table_name;
            """)
            
            tables = cursor.fetchall()
            if tables:
                for table in tables:
                    self.stdout.write(f'✓ {table[0]}')
            else:
                self.stdout.write(self.style.WARNING('No ticket tables found'))
            
            # Check indexes
            self.stdout.write(self.style.SUCCESS('\n=== Ticket Management Indexes ===\n'))
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND indexname LIKE 'portal_%'
                AND (
                    indexname LIKE '%tick%' OR
                    indexname LIKE '%agent%' OR
                    indexname LIKE '%dept%'
                )
                ORDER BY indexname;
            """)
            
            indexes = cursor.fetchall()
            if indexes:
                for idx in indexes:
                    self.stdout.write(f'✓ {idx[0]}')
            else:
                self.stdout.write(self.style.WARNING('No ticket indexes found'))
            
            # Check migration status
            self.stdout.write(self.style.SUCCESS('\n=== Migration Status ===\n'))
            cursor.execute("""
                SELECT name, applied 
                FROM django_migrations 
                WHERE app = 'portal' 
                AND name LIKE '%ticket%'
                ORDER BY applied DESC;
            """)
            
            migrations = cursor.fetchall()
            if migrations:
                for mig in migrations:
                    status = '✓ Applied' if mig[1] else '⊘ Not Applied'
                    self.stdout.write(f'{status}: {mig[0]}')
            else:
                self.stdout.write(self.style.WARNING('No ticket migrations found in django_migrations'))
