"""
Management command to seed default data
Deletes all existing data and creates fresh seed data
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction, connection
from django.contrib.auth.models import Group, Permission
from decimal import Decimal
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
        with transaction.atomic():
            # Delete in reverse order of dependencies
            WalletTransaction.objects.all().delete()
            self.stdout.write('  ✓ Deleted WalletTransaction records')
            
            Wallet.objects.all().delete()
            self.stdout.write('  ✓ Deleted Wallet records')
            
            KYC.objects.all().delete()
            self.stdout.write('  ✓ Deleted KYC records')
            
            UserPermission.objects.all().delete()
            self.stdout.write('  ✓ Deleted UserPermission records')
            
            User.objects.all().delete()
            self.stdout.write('  ✓ Deleted User records')
            
            Profile.objects.all().delete()
            self.stdout.write('  ✓ Deleted Profile records')
            
            # Note: We keep Role and Group data as they're managed by setup_roles
            # But we can reset them if needed
            self.stdout.write('  ✓ Kept Role and Group data (will be updated by setup_roles)')
    
    def _create_seed_data(self):
        """Create seed data"""
        with transaction.atomic():
            # Get roles
            admin_role = Role.objects.get(code='admin')
            super_role = Role.objects.get(code='super')
            employee_role = Role.objects.get(code='employee')
            distributor_role = Role.objects.get(code='distributor')
            retailer_role = Role.objects.get(code='retailer')
            customer_role = Role.objects.get(code='customer')
            vendor_role = Role.objects.get(code='vendor')
            
            # Create Admin Profile and User
            admin_profile = Profile.objects.create(
                name='Admin User',
                type='individual',
                email='admin@payswap.in',
                phone='+919876543210',
                status='active'
            )
            
            admin_user = User(
                first_name='Admin',
                email='admin@payswap.in',
                phone='+919876543210',
                role_code='admin',
                profile=admin_profile,
                email_verified=True,
                is_active=True,
                is_staff=True,
                is_superuser=True
            )
            admin_user.set_password('Admin@123')
            admin_user.save()
            admin_wallet = Wallet.objects.create(user=admin_user, balance=Decimal('100000.00'), status='active')
            self.stdout.write(f'  ✓ Created Admin user: {admin_user.username}')
            
            # Create Super User
            super_profile = Profile.objects.create(
                name='Super User',
                type='individual',
                email='super@payswap.in',
                phone='+919876543211',
                status='active'
            )
            super_user = User(
                first_name='Super',
                email='super@payswap.in',
                phone='+919876543211',
                role_code='super',
                profile=super_profile,
                email_verified=True,
                is_active=True
            )
            super_user.set_password('Super@123')
            super_user.save()
            super_wallet = Wallet.objects.create(user=super_user, balance=Decimal('50000.00'), status='active')
            self.stdout.write(f'  ✓ Created Super user: {super_user.username}')
            
            # Create Employee User
            employee_profile = Profile.objects.create(
                name='Employee User',
                type='individual',
                email='employee@payswap.in',
                phone='+919876543212',
                status='active'
            )
            employee_user = User(
                first_name='Employee',
                email='employee@payswap.in',
                phone='+919876543212',
                role_code='employee',
                profile=employee_profile,
                email_verified=True,
                is_active=True,
                created_by=admin_user
            )
            employee_user.set_password('Employee@123')
            employee_user.save()
            employee_wallet = Wallet.objects.create(user=employee_user, balance=Decimal('10000.00'), status='active')
            self.stdout.write(f'  ✓ Created Employee user: {employee_user.username}')
            
            # Create Distributor Profile and User
            distributor_profile = Profile.objects.create(
                name='Distributor Business',
                type='business',
                business_name='ABC Distributors',
                tax_id='GST123456789',
                email='distributor@payswap.in',
                phone='+919876543213',
                status='active'
            )
            distributor_user = User(
                first_name='Distributor',
                email='distributor@payswap.in',
                phone='+919876543213',
                role_code='distributor',
                profile=distributor_profile,
                email_verified=True,
                is_active=True,
                created_by=admin_user
            )
            distributor_user.set_password('Distributor@123')
            distributor_user.save()
            distributor_wallet = Wallet.objects.create(user=distributor_user, balance=Decimal('25000.00'), status='active')
            self.stdout.write(f'  ✓ Created Distributor user: {distributor_user.username}')
            
            # Create Retailer Profile and User
            retailer_profile = Profile.objects.create(
                name='Retailer Shop',
                type='business',
                business_name='XYZ Retail Store',
                tax_id='GST987654321',
                email='retailer@payswap.in',
                phone='+919876543214',
                status='active'
            )
            retailer_user = User(
                first_name='Retailer',
                email='retailer@payswap.in',
                phone='+919876543214',
                role_code='retailer',
                profile=retailer_profile,
                email_verified=True,
                is_active=True
            )
            retailer_user.set_password('Retailer@123')
            retailer_user.save()
            retailer_wallet = Wallet.objects.create(user=retailer_user, balance=Decimal('5000.00'), status='active')
            self.stdout.write(f'  ✓ Created Retailer user: {retailer_user.username}')
            
            # Create Customer Users
            for i in range(1, 4):
                customer_profile = Profile.objects.create(
                    name=f'Customer {i}',
                    type='individual',
                    email=f'customer{i}@payswap.in',
                    phone=f'+9198765432{10+i}',
                    status='active'
                )
                customer_user = User(
                    first_name=f'Customer{i}',
                    email=f'customer{i}@payswap.in',
                    phone=f'+9198765432{10+i}',
                    role_code='customer',
                    profile=customer_profile,
                    email_verified=True,
                    is_active=True
                )
                customer_user.set_password('Customer@123')
                customer_user.save()
                customer_wallet = Wallet.objects.create(user=customer_user, balance=Decimal(str(1000.00 * i)), status='active')
                self.stdout.write(f'  ✓ Created Customer {i} user: {customer_user.username}')
            
            # Create Vendor User
            vendor_profile = Profile.objects.create(
                name='Vendor Business',
                type='business',
                business_name='PQR Vendor Services',
                tax_id='GST555555555',
                email='vendor@payswap.in',
                phone='+919876543220',
                status='active'
            )
            vendor_user = User(
                first_name='Vendor',
                email='vendor@payswap.in',
                phone='+919876543220',
                role_code='vendor',
                profile=vendor_profile,
                email_verified=True,
                is_active=True
            )
            vendor_user.set_password('Vendor@123')
            vendor_user.save()
            vendor_wallet = Wallet.objects.create(user=vendor_user, balance=Decimal('15000.00'), status='active')
            self.stdout.write(f'  ✓ Created Vendor user: {vendor_user.username}')
            
            # Create some sample wallet transactions
            customer_wallet = Wallet.objects.filter(user__role_code='customer').first()
            self._create_sample_transactions(admin_wallet, customer_wallet)
            
            # Create some sample KYC records
            self._create_sample_kyc(customer_user, retailer_user)
    
    def _create_sample_transactions(self, wallet1, wallet2):
        """Create sample wallet transactions"""
        if wallet1 and wallet2:
            # Credit transaction
            credit_amount = Decimal('5000.00')
            WalletTransaction.objects.create(
                wallet=wallet1,
                transaction_type='credit',
                amount=credit_amount,
                balance_before=wallet1.balance,
                balance_after=wallet1.balance + credit_amount,
                reference='SEED_CREDIT_001',
                status='completed'
            )
            
            # Debit transaction
            debit_amount = Decimal('500.00')
            WalletTransaction.objects.create(
                wallet=wallet2,
                transaction_type='debit',
                amount=debit_amount,
                balance_before=wallet2.balance,
                balance_after=wallet2.balance - debit_amount,
                reference='SEED_DEBIT_001',
                status='completed'
            )
            self.stdout.write('  ✓ Created sample wallet transactions')
    
    def _create_sample_kyc(self, customer_user, retailer_user):
        """Create sample KYC records"""
        # Approved KYC for customer
        KYC.objects.create(
            user=customer_user,
            document_type='aadhaar',
            document_number='123456789012',
            document_files=['https://example.com/kyc/customer_aadhaar.pdf'],
            status='approved',
            verification_vendor='cashfree',
            verification_id='VER123456',
            verified_at=customer_user.date_joined,
            verified_by=User.objects.filter(role_code='admin').first()
        )
        customer_user.kyc_completed = True
        customer_user.kyc_status = 'approved'
        customer_user.save()
        
        # Pending KYC for retailer
        KYC.objects.create(
            user=retailer_user,
            document_type='pan',
            document_number='ABCDE1234F',
            document_files=['https://example.com/kyc/retailer_pan.pdf'],
            status='submitted',
            verification_vendor='invincible_ocean'
        )
        retailer_user.kyc_status = 'submitted'
        retailer_user.save()
        
        self.stdout.write('  ✓ Created sample KYC records')
    
    def _print_summary(self):
        """Print summary of seeded data"""
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('SEED DATA SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'Roles: {Role.objects.count()}')
        self.stdout.write(f'Profiles: {Profile.objects.count()}')
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(f'Wallets: {Wallet.objects.count()}')
        self.stdout.write(f'Wallet Transactions: {WalletTransaction.objects.count()}')
        self.stdout.write(f'KYC Records: {KYC.objects.count()}')
        self.stdout.write(self.style.SUCCESS('='*60))
        
        # Print user credentials
        self.stdout.write(self.style.WARNING('\nTest User Credentials:'))
        self.stdout.write('-' * 60)
        for user in User.objects.all().order_by('role_code'):
            self.stdout.write(f'{user.get_role_code_display():15} | {user.username:12} | Password: {self._get_password_for_role(user.role_code)}')
        self.stdout.write('-' * 60)
    
    def _get_password_for_role(self, role_code):
        """Get default password for role"""
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
