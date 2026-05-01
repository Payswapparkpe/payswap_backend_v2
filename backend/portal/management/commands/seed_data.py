"""
Management command to seed default data
Deletes all existing data and creates fresh seed data
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from decimal import Decimal
import os
import secrets
from portal.models import User, Profile, Role, Wallet, KYC, UserPermission, WalletTransaction
from portal.utils.user_utils import generate_username, get_role_prefix


class Command(BaseCommand):
    help = 'Seed default data (deletes all existing data first)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-delete',
            action='store_true',
            help='Skip deleting existing data',
        )
    
    def handle(self, *args, **options):
        skip_delete = options.get('skip_delete', False)
        self.seed_passwords = {}
        
        # Ensure migrations are applied (skip if skip_delete is True to avoid migration issues)
        if not skip_delete:
            self.stdout.write(self.style.SUCCESS('Applying migrations...'))
            try:
                call_command('migrate', verbosity=0)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Migration note: {str(e)}'))
                # Try to fake problematic migration
                try:
                    call_command('migrate', 'account', '0006', '--fake', verbosity=0)
                    call_command('migrate', verbosity=0)
                except:
                    pass
        
        if not skip_delete:
            self.stdout.write(self.style.WARNING('Deleting all existing data...'))
            self._delete_all_data()
        
        self.stdout.write(self.style.SUCCESS('Setting up roles and groups...'))
        call_command('setup_roles')
        
        self.stdout.write(self.style.SUCCESS('Creating seed data...'))
        self._create_seed_data()
        
        self.stdout.write(self.style.SUCCESS('\n✓ Seed data created successfully!'))
        self._print_summary()
    
    def _delete_all_data(self):
        """Delete all data from all tables"""
        from django.db import connection
        
        # Check if tables exist
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'portal_%'
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
        
        if not existing_tables:
            self.stdout.write('  ✓ No tables to delete (fresh database)')
            return
        
        try:
            with transaction.atomic():
                # Delete in reverse order of dependencies
                if 'portal_wallet_transaction' in existing_tables:
                    WalletTransaction.objects.all().delete()
                    self.stdout.write('  ✓ Deleted WalletTransaction records')
                
                if 'portal_wallet' in existing_tables:
                    Wallet.objects.all().delete()
                    self.stdout.write('  ✓ Deleted Wallet records')
                
                if 'portal_kyc' in existing_tables:
                    KYC.objects.all().delete()
                    self.stdout.write('  ✓ Deleted KYC records')
                
                if 'portal_user_permission' in existing_tables:
                    UserPermission.objects.all().delete()
                    self.stdout.write('  ✓ Deleted UserPermission records')
                
                # Delete users (profiles will be cascade deleted)
                if 'portal_user' in existing_tables:
                    User.objects.all().delete()
                    self.stdout.write('  ✓ Deleted User records')
                
                if 'portal_profile' in existing_tables:
                    Profile.objects.all().delete()
                    self.stdout.write('  ✓ Deleted Profile records')
                
                # Note: We keep Role and Group data as they're managed by setup_roles
                self.stdout.write('  ✓ Kept Role and Group data (will be updated by setup_roles)')
        except Exception as e:
            # If deletion fails, tables might not exist - that's okay
            self.stdout.write(f'  ⚠ Could not delete data: {str(e)}')
            self.stdout.write('  → Proceeding with fresh database setup')
    
    def _create_seed_data(self):
        """Create seed data"""
        with transaction.atomic():
            # Get roles (only these 7 exist: super_admin, admin, employee, super_distributor, distributor, retailer, customer)
            admin_role = Role.objects.get(code='admin')
            employee_role = Role.objects.get(code='employee')
            distributor_role = Role.objects.get(code='distributor')
            retailer_role = Role.objects.get(code='retailer')
            customer_role = Role.objects.get(code='customer')
            
            # Create Admin User and Profile
            admin_user = User.objects.create_user(
                username=None,  # Will be auto-generated
                password=self._seed_password('admin'),
                role_code='admin',
                is_staff=True,
                is_superuser=True,
                is_active=True,
                email_verified=True,
            )
            admin_profile = Profile.objects.create(
                user=admin_user,
                first_name='Admin',
                last_name='User',
                email='admin@payswap.in',
                phone='+919876543210',
                type='individual',
                email_verified=True,
                phone_verified=True,
                status='active'
            )
            admin_wallet = Wallet.objects.create(user=admin_user, balance=Decimal('100000.00'), status='active')
            self.stdout.write(f'  ✓ Created Admin user: {admin_user.username}')
            
            # Create Super Admin User
            super_user = User.objects.create_user(
                username=None,  # Will be auto-generated
                password=self._seed_password('super_admin'),
                role_code='super_admin',
                is_active=True,
                email_verified=True,
            )
            super_profile = Profile.objects.create(
                user=super_user,
                first_name='Super',
                last_name='Admin',
                email='super@payswap.in',
                phone='+919876543211',
                type='individual',
                email_verified=True,
                phone_verified=True,
                status='active'
            )
            super_wallet = Wallet.objects.create(user=super_user, balance=Decimal('50000.00'), status='active')
            self.stdout.write(f'  ✓ Created Super Admin user: {super_user.username}')
            
            # Create Employee User
            employee_user = User.objects.create_user(
                username=None,  # Will be auto-generated
                password=self._seed_password('employee'),
                role_code='employee',
                is_active=True,
                email_verified=True,
                created_by=admin_user,
            )
            employee_profile = Profile.objects.create(
                user=employee_user,
                first_name='Employee',
                last_name='User',
                email='employee@payswap.in',
                phone='+919876543212',
                type='individual',
                email_verified=True,
                phone_verified=True,
                status='active',
                created_by=admin_user,
            )
            employee_wallet = Wallet.objects.create(user=employee_user, balance=Decimal('10000.00'), status='active')
            self.stdout.write(f'  ✓ Created Employee user: {employee_user.username}')
            
            # Create Distributor User
            distributor_user = User.objects.create_user(
                username=None,  # Will be auto-generated
                password=self._seed_password('distributor'),
                role_code='distributor',
                is_active=True,
                email_verified=True,
                created_by=admin_user,
            )
            distributor_profile = Profile.objects.create(
                user=distributor_user,
                first_name='Distributor',
                last_name='Business',
                email='distributor@payswap.in',
                phone='+919876543213',
                type='business',
                business_name='ABC Distributors',
                gst_number='GST123456789',
                email_verified=True,
                phone_verified=True,
                status='active',
                created_by=admin_user,
            )
            distributor_wallet = Wallet.objects.create(user=distributor_user, balance=Decimal('25000.00'), status='active')
            self.stdout.write(f'  ✓ Created Distributor user: {distributor_user.username}')
            
            # Create Retailer User
            retailer_user = User.objects.create_user(
                username=None,  # Will be auto-generated
                password=self._seed_password('retailer'),
                role_code='retailer',
                is_active=True,
                email_verified=True,
            )
            retailer_profile = Profile.objects.create(
                user=retailer_user,
                first_name='Retailer',
                last_name='Shop',
                email='retailer@payswap.in',
                phone='+919876543214',
                type='business',
                business_name='XYZ Retail Store',
                gst_number='GST987654321',
                email_verified=True,
                phone_verified=True,
                status='active'
            )
            retailer_wallet = Wallet.objects.create(user=retailer_user, balance=Decimal('5000.00'), status='active')
            self.stdout.write(f'  ✓ Created Retailer user: {retailer_user.username}')
            
            # Create Customer Users
            customer_phones = ['+919876543215', '+919876543216', '+919876543217']
            for i in range(1, 4):
                customer_user = User.objects.create_user(
                    username=None,  # Will be auto-generated
                    password=self._seed_password(f'customer_{i}'),
                    role_code='customer',
                    is_active=True,
                    email_verified=True,
                )
                customer_profile = Profile.objects.create(
                    user=customer_user,
                    first_name=f'Customer{i}',
                    email=f'customer{i}@payswap.in',
                    phone=customer_phones[i-1],
                    type='individual',
                    email_verified=True,
                    phone_verified=True,
                    status='active'
                )
                customer_wallet = Wallet.objects.create(user=customer_user, balance=Decimal(str(1000.00 * i)), status='active')
                self.stdout.write(f'  ✓ Created Customer {i} user: {customer_user.username}')
            
            # Create Vendor User
            vendor_user = User.objects.create_user(
                username=None,  # Will be auto-generated
                password=self._seed_password('vendor'),
                role_code='vendor',
                is_active=True,
                email_verified=True,
            )
            vendor_profile = Profile.objects.create(
                user=vendor_user,
                first_name='Vendor',
                last_name='Business',
                email='vendor@payswap.in',
                phone='+919876543220',
                type='business',
                business_name='PQR Vendor Services',
                gst_number='GST555555555',
                email_verified=True,
                phone_verified=True,
                status='active'
            )
            vendor_wallet = Wallet.objects.create(user=vendor_user, balance=Decimal('15000.00'), status='active')
            self.stdout.write(f'  ✓ Created Vendor user: {vendor_user.username}')
            
            # Create some sample wallet transactions
            customer_wallet = Wallet.objects.filter(user__role_code='customer').first()
            if customer_wallet:
                # Credit transaction
                WalletTransaction.objects.create(
                    wallet=customer_wallet,
                    transaction_type='credit',
                    amount=Decimal('500.00'),
                    balance_before=customer_wallet.balance,
                    balance_after=customer_wallet.balance + Decimal('500.00'),
                    status='completed',
                    reference='INITIAL_CREDIT'
                )
                customer_wallet.balance += Decimal('500.00')
                customer_wallet.save()
                
                # Debit transaction
                WalletTransaction.objects.create(
                    wallet=customer_wallet,
                    transaction_type='debit',
                    amount=Decimal('200.00'),
                    balance_before=customer_wallet.balance,
                    balance_after=customer_wallet.balance - Decimal('200.00'),
                    status='completed',
                    reference='PAYMENT_DEBIT'
                )
                customer_wallet.balance -= Decimal('200.00')
                customer_wallet.save()
                self.stdout.write('  ✓ Created sample wallet transactions')
            
            # Create sample KYC records
            customer_user = User.objects.filter(role_code='customer').first()
            if customer_user:
                KYC.objects.create(
                    user=customer_user,
                    document_type='aadhaar',
                    document_number='123456789012',
                    status='approved',
                    verification_vendor='cashfree'
                )
                customer_user.kyc_completed = True
                customer_user.kyc_status = 'approved'
                customer_user.save()
                self.stdout.write('  ✓ Created sample KYC records')

    def _seed_password(self, role_key: str) -> str:
        """Use env override or secure random seed password."""
        base = os.getenv("SEED_DEFAULT_PASSWORD")
        role_specific = os.getenv(f"SEED_PASSWORD_{role_key.upper()}")
        password = (role_specific or base or secrets.token_urlsafe(12))
        self.seed_passwords[role_key] = password
        return password
    
    def _print_summary(self):
        """Print summary of created data"""
        roles_count = Role.objects.count()
        profiles_count = Profile.objects.count()
        users_count = User.objects.count()
        wallets_count = Wallet.objects.count()
        transactions_count = WalletTransaction.objects.count()
        kyc_count = KYC.objects.count()
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('SEED DATA SUMMARY'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Roles: {roles_count}')
        self.stdout.write(f'Profiles: {profiles_count}')
        self.stdout.write(f'Users: {users_count}')
        self.stdout.write(f'Wallets: {wallets_count}')
        self.stdout.write(f'Wallet Transactions: {transactions_count}')
        self.stdout.write(f'KYC Records: {kyc_count}')
        self.stdout.write('\nSeed user passwords (rotate immediately for shared environments):')
        for role_key in sorted(self.seed_passwords.keys()):
            self.stdout.write(f'  - {role_key}: {self.seed_passwords[role_key]}')
        self.stdout.write('=' * 60)
        
        self.stdout.write('\n' + '-' * 60)
        self.stdout.write(self.style.SUCCESS('Test User Credentials:'))
        self.stdout.write('-' * 60)
        
        users = User.objects.all().order_by('role_code')
        for user in users:
            profile = user.profile
            role_display = user.get_role_code_display()
            self.stdout.write(f'{role_display:15} | {user.username:15} | Password: {self._get_password_for_role(user.role_code)}')
        self.stdout.write('-' * 60)
    
    def _get_password_for_role(self, role_code):
        """Get password for role"""
        passwords = {
            'admin': 'Admin@123',
            'super': 'Super@123',
            'employee': 'Employee@123',
            'distributor': 'Distributor@123',
            'retailer': 'Retailer@123',
            'customer': 'Customer@123',
            'vendor': 'Vendor@123',
        }
        return passwords.get(role_code, 'Password@123')
