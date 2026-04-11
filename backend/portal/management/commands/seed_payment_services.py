"""
Management command to seed payment services (BBPS only).
AEPS and DMT removed — they are on Payswap Frontend, not Hub.
"""
from django.core.management.base import BaseCommand
from decimal import Decimal
from portal.models import Service, ServiceCost, ServiceIncomeConfig, BBPSBillerCategory, User


class Command(BaseCommand):
    help = 'Seed payment services: BBPS with biller categories'

    def handle(self, *args, **options):
        self.stdout.write('Seeding payment services...')
        
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.WARNING('No admin user found, using None for created_by'))
        
        # Create BBPS Service
        self.stdout.write('Creating BBPS service...')
        bbps_service, created = Service.objects.get_or_create(
            code='BBPS',
            defaults={
                'name': 'Bharat Bill Payment System',
                'description': 'BBPS service for bill payments across multiple categories',
                'status': 'active',
                'is_enabled': True,
                'requires_kyc': False,  # BBPS may not always require KYC
                'min_balance': Decimal('0.00'),
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created BBPS service'))
        else:
            self.stdout.write(f'  - BBPS service already exists')
        
        # Create BBPS Service Cost
        bbps_cost, created = ServiceCost.objects.get_or_create(
            service=bbps_service,
            is_active=True,
            defaults={
                'cost_type': 'PER_TRANSACTION',
                'cost_per_transaction': Decimal('1.50'),  # Example: ₹1.50 per transaction
                'provides_commission': True,
                'commission_on': 'partner',
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created BBPS service cost'))

        # BBPS income config (Hub earns commission from Mobikwik; do not use ServiceCost for income)
        bbps_income, created_inc = ServiceIncomeConfig.objects.get_or_create(
            service=bbps_service,
            vendor_code='mobikwik',
            is_active=True,
            defaults={
                'income_type': 'COMMISSION',
                'rate_per_txn': Decimal('1.50'),
                'rate_percentage': None,
            },
        )
        if created_inc:
            self.stdout.write(self.style.SUCCESS('  ✓ Created BBPS income config (Mobikwik commission)'))

        # 4. Create BBPS Biller Categories
        self.stdout.write('Creating BBPS biller categories...')
        biller_categories = [
            {
                'category_code': 'ELECTRICITY',
                'category_name': 'Electricity',
                'category_type': 'ELECTRICITY',
                'default_commission_percentage': Decimal('0.25'),
                'base_cost': Decimal('1.00'),
                'description': 'Electricity bill payments'
            },
            {
                'category_code': 'WATER',
                'category_name': 'Water',
                'category_type': 'WATER',
                'default_commission_percentage': Decimal('0.25'),
                'base_cost': Decimal('1.00'),
                'description': 'Water bill payments'
            },
            {
                'category_code': 'GAS',
                'category_name': 'Gas',
                'category_type': 'GAS',
                'default_commission_percentage': Decimal('0.25'),
                'base_cost': Decimal('1.00'),
                'description': 'Gas bill payments'
            },
            {
                'category_code': 'MOBILE_PREPAID',
                'category_name': 'Mobile Prepaid',
                'category_type': 'MOBILE_PREPAID',
                'default_commission_percentage': Decimal('0.50'),
                'base_cost': Decimal('0.50'),
                'description': 'Mobile prepaid recharge'
            },
            {
                'category_code': 'MOBILE_POSTPAID',
                'category_name': 'Mobile Postpaid',
                'category_type': 'MOBILE_POSTPAID',
                'default_commission_percentage': Decimal('0.30'),
                'base_cost': Decimal('1.00'),
                'description': 'Mobile postpaid bill payments'
            },
            {
                'category_code': 'LANDLINE',
                'category_name': 'Landline',
                'category_type': 'LANDLINE',
                'default_commission_percentage': Decimal('0.30'),
                'base_cost': Decimal('1.00'),
                'description': 'Landline bill payments'
            },
            {
                'category_code': 'BROADBAND',
                'category_name': 'Broadband',
                'category_type': 'BROADBAND',
                'default_commission_percentage': Decimal('0.30'),
                'base_cost': Decimal('1.00'),
                'description': 'Broadband bill payments'
            },
            {
                'category_code': 'DTH',
                'category_name': 'DTH',
                'category_type': 'DTH',
                'default_commission_percentage': Decimal('0.50'),
                'base_cost': Decimal('0.50'),
                'description': 'DTH recharge and bill payments'
            },
            {
                'category_code': 'INSURANCE',
                'category_name': 'Insurance',
                'category_type': 'INSURANCE',
                'default_commission_percentage': Decimal('1.00'),
                'base_cost': Decimal('2.00'),
                'description': 'Insurance premium payments'
            },
            {
                'category_code': 'LOAN',
                'category_name': 'Loan',
                'category_type': 'LOAN',
                'default_commission_percentage': Decimal('0.50'),
                'base_cost': Decimal('1.50'),
                'description': 'Loan EMI payments'
            },
            {
                'category_code': 'CREDIT_CARD',
                'category_name': 'Credit Card',
                'category_type': 'CREDIT_CARD',
                'default_commission_percentage': Decimal('0.50'),
                'base_cost': Decimal('1.50'),
                'description': 'Credit card bill payments'
            },
            {
                'category_code': 'FASTAG',
                'category_name': 'Fastag',
                'category_type': 'FASTAG',
                'default_commission_percentage': Decimal('0.25'),
                'base_cost': Decimal('0.50'),
                'description': 'Fastag recharge'
            },
            {
                'category_code': 'MUNICIPAL',
                'category_name': 'Municipal',
                'category_type': 'MUNICIPAL',
                'default_commission_percentage': Decimal('0.25'),
                'base_cost': Decimal('1.00'),
                'description': 'Municipal tax and bill payments'
            },
            {
                'category_code': 'EDUCATION',
                'category_name': 'Education',
                'category_type': 'EDUCATION',
                'default_commission_percentage': Decimal('0.30'),
                'base_cost': Decimal('1.00'),
                'description': 'Education fee payments'
            },
            {
                'category_code': 'HEALTHCARE',
                'category_name': 'Healthcare',
                'category_type': 'HEALTHCARE',
                'default_commission_percentage': Decimal('0.30'),
                'base_cost': Decimal('1.00'),
                'description': 'Healthcare bill payments'
            },
            {
                'category_code': 'OTHER',
                'category_name': 'Other',
                'category_type': 'OTHER',
                'default_commission_percentage': Decimal('0.25'),
                'base_cost': Decimal('1.00'),
                'description': 'Other bill payments'
            },
        ]
        
        for category_data in biller_categories:
            category, created = BBPSBillerCategory.objects.get_or_create(
                service=bbps_service,
                category_code=category_data['category_code'],
                defaults={
                    'category_name': category_data['category_name'],
                    'category_type': category_data['category_type'],
                    'commission_type': 'REVENUE_SHARE',
                    'default_commission_percentage': category_data['default_commission_percentage'],
                    'default_fixed_commission': Decimal('0.00'),
                    'base_cost': category_data['base_cost'],
                    'description': category_data['description'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created BBPS category: {category_data["category_name"]}'))
            else:
                self.stdout.write(f'  - BBPS category {category_data["category_name"]} already exists')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Payment services seeding completed!'))
        self.stdout.write(f'\nSummary: BBPS service + {len(biller_categories)} biller categories')
