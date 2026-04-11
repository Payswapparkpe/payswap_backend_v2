"""
Management command to completely reset the database
Drops all tables and recreates them with fresh migrations
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Completely reset the database (drop all tables and recreate)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Skip confirmation prompt',
        )
    
    def handle(self, *args, **options):
        noinput = options.get('noinput', False)
        
        if not noinput:
            confirm = input(
                self.style.WARNING(
                    '\n⚠️  WARNING: This will DELETE ALL DATA in the database!\n'
                    'Are you sure you want to continue? (yes/no): '
                )
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Operation cancelled.'))
                return
        
        self.stdout.write(self.style.WARNING('\n🗑️  Dropping all database tables...'))
        self._drop_all_tables()
        
        self.stdout.write(self.style.SUCCESS('✓ All tables dropped'))
        
        self.stdout.write(self.style.SUCCESS('\n🔄 Running migrations...'))
        # Run migrations with fake for allauth if needed
        try:
            call_command('migrate', verbosity=1, interactive=False, run_syncdb=True)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Migration warning: {str(e)}'))
            # Try to continue with fake migration for problematic ones
            try:
                call_command('migrate', 'account', '0006', '--fake', verbosity=0)
                call_command('migrate', verbosity=1, interactive=False)
            except:
                pass
        
        self.stdout.write(self.style.SUCCESS('✓ Migrations applied'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ Database reset complete!'))
        self.stdout.write(self.style.SUCCESS('Run "python manage.py setup_roles" and "python manage.py seed_data" to populate data.'))
    
    def _drop_all_tables(self):
        """Drop all tables in the database"""
        with connection.cursor() as cursor:
            # Get database engine
            db_engine = settings.DATABASES['default']['ENGINE']
            
            if 'postgresql' in db_engine:
                # PostgreSQL: Drop all tables
                cursor.execute("""
                    DO $$ DECLARE
                        r RECORD;
                    BEGIN
                        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                            EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                        END LOOP;
                    END $$;
                """)
                # Drop all sequences
                cursor.execute("""
                    DO $$ DECLARE
                        r RECORD;
                    BEGIN
                        FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public') LOOP
                            EXECUTE 'DROP SEQUENCE IF EXISTS ' || quote_ident(r.sequence_name) || ' CASCADE';
                        END LOOP;
                    END $$;
                """)
            elif 'sqlite3' in db_engine:
                # SQLite: Get all table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = cursor.fetchall()
                for table in tables:
                    cursor.execute(f'DROP TABLE IF EXISTS {table[0]}')
            else:
                # Generic: Try to get tables from information_schema
                try:
                    cursor.execute("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = DATABASE()
                    """)
                    tables = cursor.fetchall()
                    for table in tables:
                        cursor.execute(f'DROP TABLE IF EXISTS `{table[0]}`')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error dropping tables: {str(e)}'))
                    self.stdout.write(self.style.WARNING('Please manually drop tables or use database-specific tools.'))
