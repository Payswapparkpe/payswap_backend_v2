"""
Management command to seed initial services
"""
from django.core.management.base import BaseCommand
from portal.models import Service


class Command(BaseCommand):
    help = 'Seed initial services for API integration'

    def handle(self, *args, **options):
        services_data = [
            {
                'name': 'BBPS',
                'code': 'BBPS',
                'description': 'Bharat Bill Payment System - Bill payment services',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'AEPS',
                'code': 'AEPS',
                'description': 'Aadhaar Enabled Payment System - Cash withdrawal and balance enquiry',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'DMT',
                'code': 'DMT',
                'description': 'Domestic Money Transfer - Money transfer services',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'Recharges',
                'code': 'RECHARGES',
                'description': 'Mobile, DTH, and Data Recharge services',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'Gift Voucher',
                'code': 'GIFT_VOUCHER',
                'description': 'Gift Voucher purchase and redemption services',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'Prepaid Card',
                'code': 'PREPAID_CARD',
                'description': 'Prepaid Card services - Purchase and management',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'Stock Vouchers',
                'code': 'STOCK_VOUCHERS',
                'description': 'Stock Vouchers - Purchase and redemption services',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'Offline BBPS',
                'code': 'OFFLINE_BBPS',
                'description': 'Offline Bharat Bill Payment System - Offline bill payment services',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'Verification API',
                'code': 'VERIFICATION_API',
                'description': 'Verification API - Document and identity verification services with support for multiple vendors (Cashfree, etc.)',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'Verification Service',
                'code': 'VERIFICATION',
                'description': 'Verification Service - General verification and validation services',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'SMS/IVR Gateway',
                'code': 'SMS_IVR_GATEWAY',
                'description': 'SMS and IVR Gateway services - Send SMS, OTP, and manage IVR calls with support for multiple vendors (Kaleyra, etc.)',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'Payment Gateway',
                'code': 'PAYMENT_GATEWAY',
                'description': 'Payment Gateway services - Process payments, create orders, manage refunds with support for multiple vendors (Cashfree PG, etc.)',
                'status': 'pending',
                'requires_kyc': False,  # Admin has direct access, KYC check at user level when granting permissions
            },
            {
                'name': 'Instantpay',
                'code': 'INSTANTPAY',
                'description': 'Instantpay API - Identity verification, Banking, Payouts, AePS, Collect, Tax, AI/ML, and more (https://developers.instantpay.in)',
                'status': 'pending',
                'requires_kyc': False,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for service_data in services_data:
            service, created = Service.objects.update_or_create(
                code=service_data['code'],
                defaults={
                    'name': service_data['name'],
                    'description': service_data['description'],
                    'status': service_data['status'],
                    'requires_kyc': service_data['requires_kyc'],
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created service: {service.name} ({service.code})')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'→ Updated service: {service.name} ({service.code})')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Successfully seeded services! Created: {created_count}, Updated: {updated_count}'
            )
        )
