"""
Management command to seed payment services (AEPS, DMT, BBPS)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from portal.models import Service, ServiceCost, BBPSBillerCategory, RBIRuleConfiguration, User


class Command(BaseCommand):
    help = 'Seed payment services: AEPS, DMT, BBPS with their configurations'

    def handle(self, *args, **options):
        self.stdout.write('Seeding payment services...')
        
        # Get or create admin user for created_by
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.WARNING('No admin user found, using None for created_by'))
        
        # 1. Create AEPS Service
        self.stdout.write('Creating AEPS service...')
        aeps_service, created = Service.objects.get_or_create(
            code='AEPS',
            defaults={
                'name': 'Aadhaar Enabled Payment System',
                'description': 'AEPS service for cash withdrawal, balance enquiry, and mini statement using Aadhaar',
                'status': 'active',
                'is_enabled': True,
                'requires_kyc': True,
                'min_balance': Decimal('0.00'),
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created AEPS service'))
        else:
            self.stdout.write(f'  - AEPS service already exists')
        
        # Create AEPS Service Cost
        aeps_cost, created = ServiceCost.objects.get_or_create(
            service=aeps_service,
            is_active=True,
            defaults={
                'cost_type': 'PER_TRANSACTION',
                'cost_per_transaction': Decimal('2.00'),  # Example: ₹2 per transaction
                'provides_commission': True,
                'commission_on': 'partner',
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created AEPS service cost'))
        
        # 2. Create DMT Service
        self.stdout.write('Creating DMT service...')
        dmt_service, created = Service.objects.get_or_create(
            code='DMT',
            defaults={
                'name': 'Domestic Money Transfer',
                'description': 'DMT service for money transfer (sender charged as per RBI rules)',
                'status': 'active',
                'is_enabled': True,
                'requires_kyc': True,
                'min_balance': Decimal('0.00'),
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created DMT service'))
        else:
            self.stdout.write(f'  - DMT service already exists')
        
        # Create DMT Service Cost
        dmt_cost, created = ServiceCost.objects.get_or_create(
            service=dmt_service,
            is_active=True,
            defaults={
                'cost_type': 'PERCENTAGE',
                'base_cost': Decimal('0.00'),
                'cost_percentage': Decimal('0.50'),  # Example: 0.5% of transaction amount
                'provides_commission': True,
                'commission_on': 'sender',  # Sender is charged as per RBI rules
                'created_by': admin_user,
                'notes': 'RBI Rule: Sender is charged for DMT transactions. Commission is credited to partner.'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created DMT service cost'))
        
        # 3. Create BBPS Service
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
        
        # 5. Create RBI Rule for DMT (Sender Charged)
        self.stdout.write('Creating RBI rule for DMT (sender charged)...')
        dmt_rbi_rule, created = RBIRuleConfiguration.objects.get_or_create(
            service=dmt_service,
            rule_name='DMT Sender Charged Rule',
            defaults={
                'rule_description': 'As per RBI guidelines, the sender is charged for DMT transactions. Commission is credited to the partner.',
                'rule_config': {
                    'charges_on': 'sender',
                    'max_amount': 10000.00,
                    'min_amount': 1.00,
                    'charge_type': 'percentage',
                    'charge_percentage': 0.50
                },
                'rbi_circular_reference': 'RBI/2019-20/123 - Guidelines for Money Transfer Services',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created RBI rule for DMT'))
        else:
            self.stdout.write(f'  - RBI rule for DMT already exists')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Payment services seeding completed!'))
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'  - AEPS: {aeps_service.name}')
        self.stdout.write(f'  - DMT: {dmt_service.name} (RBI Rule: Sender Charged)')
        self.stdout.write(f'  - BBPS: {bbps_service.name}')
        self.stdout.write(f'  - BBPS Categories: {len(biller_categories)}')
