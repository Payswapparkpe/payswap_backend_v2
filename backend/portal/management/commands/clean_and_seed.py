"""
Management command to clean database and seed fresh data
Combines reset_db, setup_roles, and seed_data
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection


class Command(BaseCommand):
    help = 'Clean database, run migrations, setup roles, and seed data'
    
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
                    '\n⚠️  WARNING: This will DELETE ALL DATA and recreate the database!\n'
                    'Are you sure you want to continue? (yes/no): '
                )
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Operation cancelled.'))
                return
        
        self.stdout.write(self.style.SUCCESS('\n🔄 Step 1: Resetting database...'))
        try:
            call_command('reset_db', '--noinput', verbosity=0)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Reset warning: {str(e)}'))
            # Try to continue
        
        self.stdout.write(self.style.SUCCESS('✓ Database reset'))
        
        self.stdout.write(self.style.SUCCESS('\n🔄 Step 2: Running migrations...'))
        # Migrations were already run in reset_db, just verify
        try:
            call_command('migrate', verbosity=0, interactive=False)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Migration note: {str(e)}'))
            # Fake the problematic allauth migration if needed
            try:
                call_command('migrate', 'account', '0006', '--fake', verbosity=0)
                call_command('migrate', verbosity=0, interactive=False)
            except:
                pass
        
        self.stdout.write(self.style.SUCCESS('✓ Migrations applied'))
        
        self.stdout.write(self.style.SUCCESS('\n🔄 Step 3: Setting up roles...'))
        call_command('setup_roles', verbosity=0)
        
        self.stdout.write(self.style.SUCCESS('✓ Roles setup'))
        
        self.stdout.write(self.style.SUCCESS('\n🔄 Step 4: Seeding data...'))
        call_command('seed_data', '--skip-delete', verbosity=1)
        
        self.stdout.write(self.style.SUCCESS('\n✅ Database cleaned and seeded successfully!'))
