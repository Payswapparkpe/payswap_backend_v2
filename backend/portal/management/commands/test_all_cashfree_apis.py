"""
Management command to test all Cashfree APIs and log results
This will help identify which APIs are working and which are not connected to the logging system
"""
from django.core.management.base import BaseCommand
from portal.services.verification_api import VerificationAPIService
from portal.models import CashfreeAPILog
from django.utils import timezone
from datetime import timedelta
import uuid


class Command(BaseCommand):
    help = 'Test all Cashfree APIs and verify logging is working'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='User ID to use for logging (optional)'
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        request_id = str(uuid.uuid4())
        
        self.stdout.write(self.style.SUCCESS('Starting Cashfree API tests...'))
        self.stdout.write(f'Request ID: {request_id}')
        self.stdout.write('=' * 80)
        
        verification_service = VerificationAPIService()
        log_params = {
            'user_id': user_id,
            'request_id': request_id,
            'client_ip': '127.0.0.1',
            'user_agent': 'Django Management Command'
        }
        
        # Define all APIs to test with their test data
        # Note: Some APIs require real data (images, valid numbers) - these will be marked as NEEDS_DATA
        api_tests = [
            # Basic Document Verification APIs
            {
                'name': 'PAN Verification',
                'api_type': 'pan',
                'method': verification_service.verify_pan,
                'args': ['ABCDE1234F'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Aadhaar Verification',
                'api_type': 'aadhaar',
                'method': verification_service.verify_aadhaar,
                'args': ['123456789012'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Bank Account Verification',
                'api_type': 'bank',
                'method': verification_service.verify_bank_account,
                'args': ['1234567890', 'HDFC0001234'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Phone Verification',
                'api_type': 'phone',
                'method': verification_service.verify_phone,
                'args': ['+919876543210'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Email Verification',
                'api_type': 'email',
                'method': verification_service.verify_email,
                'args': ['test@example.com'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Driving License Verification',
                'api_type': 'driving_license',
                'method': verification_service.verify_driving_license,
                'args': ['DL1234567890'],
                'kwargs': {'dob': '1990-01-01'},
                'needs_data': False
            },
            {
                'name': 'Voter ID Verification',
                'api_type': 'voter_id',
                'method': verification_service.verify_voter_id,
                'args': ['ABC1234567'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Passport Verification',
                'api_type': 'passport',
                'method': verification_service.verify_passport,
                'args': ['A1234567'],
                'kwargs': {'dob': '1990-01-01'},
                'needs_data': False
            },
            {
                'name': 'GST Verification',
                'api_type': 'gst',
                'method': verification_service.verify_gst,
                'args': ['27AABCU9603R1ZX'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'CIN Verification',
                'api_type': 'cin',
                'method': verification_service.verify_cin,
                'args': ['U12345AB1234PLC123456'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'IFSC Verification',
                'api_type': 'ifsc',
                'method': verification_service.verify_ifsc,
                'args': ['HDFC0001234'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Vehicle RC Verification',
                'api_type': 'vehicle_rc',
                'method': verification_service.verify_vehicle_rc,
                'args': ['KA01MW8769'],
                'kwargs': {},
                'needs_data': False
            },
            
            # Advanced Aadhaar APIs
            {
                'name': 'Aadhaar OCR',
                'api_type': 'aadhaar_ocr',
                'method': verification_service.verify_aadhaar_ocr,
                'args': ['dGVzdF9hYWRoYWFyX2ltYWdlX2RhdGE='],  # Base64 placeholder
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real Aadhaar card image (Base64 encoded)'
            },
            {
                'name': 'Aadhaar Masking',
                'api_type': 'aadhaar_masking',
                'method': verification_service.verify_aadhaar_masking,
                'args': ['123456789012'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Offline Aadhaar Send OTP',
                'api_type': 'offline_aadhaar_send_otp',
                'method': verification_service.offline_aadhaar_send_otp,
                'args': ['123456789012'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Offline Aadhaar Verify OTP',
                'api_type': 'offline_aadhaar_verify_otp',
                'method': verification_service.offline_aadhaar_verify_otp,
                'args': ['123456', 'test_verification_id_123'],  # OTP, verification_id
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real verification_id from send_otp response and OTP from mobile'
            },
            
            # Advanced PAN APIs
            {
                'name': 'PAN Advance',
                'api_type': 'pan_advance',
                'method': verification_service.verify_pan_advance,
                'args': ['ABCDE1234F'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'PAN OCR',
                'api_type': 'pan_ocr',
                'method': verification_service.verify_pan_ocr,
                'args': ['dGVzdF9wYW5faW1hZ2VfZGF0YQ=='],  # Base64 placeholder
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real PAN card image (Base64 encoded)'
            },
            {
                'name': 'PAN to GSTIN',
                'api_type': 'pan_to_gstin',
                'method': verification_service.verify_pan_to_gstin,
                'args': ['ABCDE1234F'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Bulk PAN Verification',
                'api_type': 'pan_bulk',
                'method': verification_service.verify_pan_bulk,
                'args': [[{'pan': 'ABCDE1234F'}, {'pan': 'FGHIJ5678K'}]],
                'kwargs': {},
                'needs_data': False
            },
            
            # DigiLocker APIs
            {
                'name': 'DigiLocker Create URL',
                'api_type': 'digilocker_create_url',
                'method': verification_service.digilocker_create_url,
                'args': ['https://example.com/callback'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'DigiLocker Get Status',
                'api_type': 'digilocker_get_status',
                'method': verification_service.digilocker_get_status,
                'args': ['test_verification_id_123'],
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real verification_id from create_url response'
            },
            {
                'name': 'DigiLocker Get Document',
                'api_type': 'digilocker_get_document',
                'method': verification_service.digilocker_get_document,
                'args': ['test_verification_id_123', 'aadhaar'],
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real verification_id from create_url response'
            },
            
            # E-sign APIs
            {
                'name': 'E-sign Create Signature',
                'api_type': 'esign_create_signature',
                'method': verification_service.esign_create_signature,
                'args': ['dGVzdF9kb2N1bWVudF9kYXRh'],  # Base64 document
                'kwargs': {'signers': [{'name': 'Test User', 'email': 'test@example.com', 'phone': '9999999999', 'sign_positions': [{'page': 1, 'x': 100, 'y': 200}]}]},
                'needs_data': True,
                'data_required': 'Real document (Base64) and signer details'
            },
            {
                'name': 'E-sign Get Status',
                'api_type': 'esign_get_status',
                'method': verification_service.esign_get_status,
                'args': ['test_verification_id_123'],
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real verification_id from create_signature response'
            },
            {
                'name': 'E-sign Upload Document',
                'api_type': 'esign_upload_document',
                'method': verification_service.esign_upload_document,
                'args': ['dGVzdF9kb2N1bWVudF9kYXRh'],  # Base64 document
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real document (Base64 encoded)'
            },
            
            # Advanced Verification APIs
            {
                'name': 'Advance Employment',
                'api_type': 'advance_employment',
                'method': verification_service.verify_advance_employment,
                'args': [],
                'kwargs': {'uan': '123456789012', 'pan': 'ABCDE1234F'},
                'needs_data': False
            },
            {
                'name': 'Reverse Penny Drop',
                'api_type': 'reverse_penny_drop',
                'method': verification_service.verify_reverse_penny_drop,
                'args': ['1234567890', 'HDFC0001234'],
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'Reverse Penny Drop Status',
                'api_type': 'reverse_penny_drop_status',
                'method': verification_service.get_reverse_penny_drop_status,
                'args': ['test_verification_id_123'],
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real verification_id from reverse_penny_drop response'
            },
            {
                'name': 'Reverse Geocoding',
                'api_type': 'reverse_geocoding',
                'method': verification_service.verify_reverse_geocoding,
                'args': [28.6139, 77.2090],  # Delhi coordinates
                'kwargs': {},
                'needs_data': False
            },
            {
                'name': 'IP Verification',
                'api_type': 'ip_verification',
                'method': verification_service.verify_ip_address,
                'args': ['8.8.8.8'],  # Google DNS
                'kwargs': {},
                'needs_data': False
            },
            
            # Biometric KYC APIs
            {
                'name': 'Face Liveness',
                'api_type': 'face_liveness',
                'method': verification_service.verify_face_liveness,
                'args': ['dGVzdF9pbWFnZV9kYXRh'],  # Base64 placeholder
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real face image (Base64 encoded)'
            },
            {
                'name': 'Face Match',
                'api_type': 'face_match',
                'method': verification_service.verify_face_match,
                'args': ['dGVzdF9pbWFnZTFfZGF0YQ==', 'dGVzdF9pbWFnZTJfZGF0YQ=='],  # Base64 placeholders
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Two real face images (Base64 encoded)'
            },
            {
                'name': 'Name Match',
                'api_type': 'name_match',
                'method': verification_service.verify_name_match,
                'args': ['John Doe', 'John D.'],
                'kwargs': {},
                'needs_data': False
            },
            
            # OCR APIs
            {
                'name': 'Smart OCR',
                'api_type': 'smart_ocr',
                'method': verification_service.smart_ocr,
                'args': ['pan', 'dGVzdF9kb2N1bWVudF9pbWFnZQ=='],  # document_type, base64 image
                'kwargs': {},
                'needs_data': True,
                'data_required': 'Real document image (Base64 encoded)'
            },
        ]
        
        results = []
        needs_data_apis = []
        
        for test in api_tests:
            self.stdout.write(f"\nTesting: {test['name']} ({test['api_type']})")
            if test.get('needs_data'):
                self.stdout.write(self.style.WARNING(f"  ⚠ This API needs real data: {test.get('data_required', 'N/A')}"))
            self.stdout.write('-' * 80)
            
            try:
                # Call the API method with test data
                result = test['method'](*test['args'], **test['kwargs'], **log_params)
                
                # Check if log was created
                last_5_min = timezone.now() - timedelta(minutes=5)
                log_exists = CashfreeAPILog.objects.filter(
                    api_type=test['api_type'],
                    request_id=request_id,
                    timestamp__gte=last_5_min
                ).exists()
                
                if log_exists:
                    log = CashfreeAPILog.objects.filter(
                        api_type=test['api_type'],
                        request_id=request_id,
                        timestamp__gte=last_5_min
                    ).first()
                    
                    status_icon = '✓' if log.status == 'success' else '✗'
                    self.stdout.write(
                        self.style.SUCCESS(f'{status_icon} API called successfully')
                    )
                    self.stdout.write(f'  Status: {log.status}')
                    self.stdout.write(f'  Log ID: {log.id}')
                    self.stdout.write(f'  Endpoint: {log.endpoint}')
                    if log.error_message:
                        self.stdout.write(
                            self.style.WARNING(f'  Error: {log.error_message[:100]}')
                        )
                    
                    results.append({
                        'api_type': test['api_type'],
                        'name': test['name'],
                        'status': 'SUCCESS - Logged',
                        'log_id': log.id,
                        'log_status': log.status,
                        'error': log.error_message,
                        'needs_data': test.get('needs_data', False),
                        'data_required': test.get('data_required', None)
                    })
                    if test.get('needs_data') and log.status == 'error':
                        needs_data_apis.append({
                            'name': test['name'],
                            'api_type': test['api_type'],
                            'data_required': test.get('data_required', 'N/A'),
                            'error': log.error_message[:100] if log.error_message else 'Unknown error'
                        })
                else:
                    self.stdout.write(
                        self.style.ERROR('✗ API called but NO LOG CREATED!')
                    )
                    self.stdout.write(
                        self.style.WARNING('  This API is NOT connected to logging system!')
                    )
                    results.append({
                        'api_type': test['api_type'],
                        'name': test['name'],
                        'status': 'ERROR - No Log',
                        'log_id': None,
                        'log_status': None,
                        'error': 'No log entry created',
                        'needs_data': test.get('needs_data', False),
                        'data_required': test.get('data_required', None)
                    })
                
                # Show API response summary
                if isinstance(result, dict):
                    response_status = result.get('status', 'unknown')
                    self.stdout.write(f'  API Response Status: {response_status}')
                    
            except Exception as e:
                error_msg = str(e)
                self.stdout.write(
                    self.style.ERROR(f'✗ API call failed: {error_msg[:200]}')
                )
                
                # Check if error was logged
                last_5_min = timezone.now() - timedelta(minutes=5)
                log_exists = CashfreeAPILog.objects.filter(
                    api_type=test['api_type'],
                    request_id=request_id,
                    timestamp__gte=last_5_min
                ).exists()
                
                if log_exists:
                    log = CashfreeAPILog.objects.filter(
                        api_type=test['api_type'],
                        request_id=request_id,
                        timestamp__gte=last_5_min
                    ).first()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Error was logged (Log ID: {log.id})')
                    )
                    results.append({
                        'api_type': test['api_type'],
                        'name': test['name'],
                        'status': 'ERROR - But Logged',
                        'log_id': log.id,
                        'log_status': log.status,
                        'error': error_msg,
                        'needs_data': test.get('needs_data', False),
                        'data_required': test.get('data_required', None)
                    })
                    if test.get('needs_data'):
                        needs_data_apis.append({
                            'name': test['name'],
                            'api_type': test['api_type'],
                            'data_required': test.get('data_required', 'N/A'),
                            'error': error_msg[:100]
                        })
                else:
                    self.stdout.write(
                        self.style.ERROR('  ✗ Error was NOT logged!')
                    )
                    results.append({
                        'api_type': test['api_type'],
                        'name': test['name'],
                        'status': 'ERROR - No Log',
                        'log_id': None,
                        'log_status': None,
                        'error': error_msg,
                        'needs_data': test.get('needs_data', False),
                        'data_required': test.get('data_required', None)
                    })
        
        # Summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('\nTEST SUMMARY'))
        self.stdout.write('=' * 80)
        
        success_count = sum(1 for r in results if 'SUCCESS' in r['status'] or 'But Logged' in r['status'])
        no_log_count = sum(1 for r in results if 'No Log' in r['status'])
        
        self.stdout.write(f'\nTotal APIs tested: {len(results)}')
        self.stdout.write(
            self.style.SUCCESS(f'APIs with logging: {success_count}')
        )
        self.stdout.write(
            self.style.ERROR(f'APIs WITHOUT logging: {no_log_count}')
        )
        
        if no_log_count > 0:
            self.stdout.write('\n' + self.style.ERROR('APIs NOT connected to logging:'))
            for r in results:
                if 'No Log' in r['status']:
                    self.stdout.write(f'  - {r["name"]} ({r["api_type"]})')
        
        # APIs that need real data
        if needs_data_apis:
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.WARNING('\nAPIs THAT NEED REAL DATA:'))
            self.stdout.write('=' * 80)
            for api in needs_data_apis:
                self.stdout.write(f'\n  • {api["name"]} ({api["api_type"]})')
                self.stdout.write(f'    Required: {api["data_required"]}')
                if api.get('error'):
                    self.stdout.write(f'    Error: {api["error"]}')
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('Check /logs/?category=cashfree to view all logs')
        self.stdout.write('=' * 80)
