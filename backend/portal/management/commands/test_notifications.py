"""
Management command to test SMS and Email notifications
"""
from django.core.management.base import BaseCommand
from portal.services.notification_service_v2 import NotificationServiceV2
from portal.services.otp_service import OTPService
from portal.models import User, Profile
from portal.utils.phone_utils import normalize_phone_number


class Command(BaseCommand):
    help = 'Test SMS and Email notification functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            type=str,
            help='Phone number to test SMS (will be normalized)',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to test email',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID to use for testing (will use user\'s phone/email)',
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Send synchronously (for testing) instead of async',
        )
        parser.add_argument(
            '--test-otp',
            action='store_true',
            help='Test OTP sending',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Testing Notification Service'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        notification_service = NotificationServiceV2()
        async_send = not options.get('sync', False)
        
        # Get phone and email
        phone = options.get('phone')
        email = options.get('email')
        user_id = options.get('user_id')
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                if hasattr(user, 'profile') and user.profile:
                    if not phone:
                        phone = user.profile.phone
                    if not email:
                        email = user.profile.email
                    self.stdout.write(f'Using user: {user.username} (ID: {user.id})')
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User with ID {user_id} not found'))
                return
        
        # Test phone normalization
        if phone:
            try:
                normalized = normalize_phone_number(phone)
                self.stdout.write(self.style.SUCCESS(f'\n✓ Phone normalization:'))
                self.stdout.write(f'  Input:    {phone}')
                self.stdout.write(f'  Normalized: {normalized} (format: 91XXXXXXXXXX, no +)')
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f'\n✗ Phone normalization failed: {e}'))
                return
        
        # Test SMS
        if phone:
            self.stdout.write(self.style.SUCCESS(f'\n--- Testing SMS ---'))
            self.stdout.write(f'Phone: {phone}')
            self.stdout.write(f'Mode: {"Async (Celery)" if async_send else "Sync"}')
            
            try:
                result = notification_service.send_sms(
                    phone_number=phone,
                    message='Test SMS from Payswap notification service. This is a test message.',
                    user_id=user_id,
                    async_send=async_send
                )
                
                if result.get('success'):
                    if async_send:
                        self.stdout.write(self.style.SUCCESS(f'✓ SMS queued successfully'))
                        self.stdout.write(f'  Task ID: {result.get("task_id")}')
                        self.stdout.write(f'  Check Celery worker logs for delivery status')
                    else:
                        self.stdout.write(self.style.SUCCESS(f'✓ SMS sent successfully'))
                        self.stdout.write(f'  Response: {result.get("message")}')
                else:
                    self.stdout.write(self.style.ERROR(f'✗ SMS failed: {result.get("message")}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ SMS error: {str(e)}'))
        
        # Test OTP
        if options.get('test_otp') and phone:
            self.stdout.write(self.style.SUCCESS(f'\n--- Testing OTP ---'))
            self.stdout.write(f'Phone: {phone}')
            self.stdout.write(f'Mode: {"Async (Celery)" if async_send else "Sync"}')
            
            try:
                otp_service = OTPService()
                success, message = otp_service.send_otp(phone, user_id=user_id, async_send=async_send)
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f'✓ OTP sent successfully'))
                    self.stdout.write(f'  OTP Code: {message}')
                    if async_send:
                        self.stdout.write(f'  Check Celery worker logs for delivery status')
                else:
                    self.stdout.write(self.style.ERROR(f'✗ OTP failed: {message}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ OTP error: {str(e)}'))
        
        # Test Email
        if email:
            self.stdout.write(self.style.SUCCESS(f'\n--- Testing Email ---'))
            self.stdout.write(f'Email: {email}')
            self.stdout.write(f'Mode: {"Async (Celery)" if async_send else "Sync"}')
            
            try:
                result = notification_service.send_email(
                    to_email=email,
                    subject='Test Email from Payswap',
                    template_name='portal/emails/verification.html',
                    context={
                        'user': {'username': 'Test User'},
                        'verification_url': 'https://payswap.in/verify/test-token'
                    },
                    user_id=user_id,
                    async_send=async_send
                )
                
                if result.get('success'):
                    if async_send:
                        self.stdout.write(self.style.SUCCESS(f'✓ Email queued successfully'))
                        self.stdout.write(f'  Task ID: {result.get("task_id")}')
                        self.stdout.write(f'  Check Celery worker logs for delivery status')
                    else:
                        self.stdout.write(self.style.SUCCESS(f'✓ Email sent successfully'))
                        self.stdout.write(f'  Response: {result.get("message")}')
                else:
                    self.stdout.write(self.style.ERROR(f'✗ Email failed: {result.get("message")}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Email error: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('Testing Complete'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        if async_send:
            self.stdout.write(self.style.WARNING('\nNote: Notifications were sent asynchronously.'))
            self.stdout.write('Check Celery worker logs to see delivery status.')
            self.stdout.write('To test synchronously, use --sync flag.')
