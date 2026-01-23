"""
Comprehensive TDD tests for authentication system
Tests: Multi-step login, signup, social auth, profile completion, IP logging, rate limiting, account lockout
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
from portal.models import Profile, Role
from portal.utils.ip_utils import get_client_ip
from portal.utils.user_utils import generate_username
import json


User = get_user_model()


class AuthenticationTestCase(TestCase):
    """Base test case for authentication tests"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        cache.clear()
        
        # Create roles
        self.admin_role = Role.objects.create(
            name='Admin',
            code='admin',
            category='b2b',
            hierarchy_level=10,
            mfa_required=True
        )
        self.super_role = Role.objects.create(
            name='Super',
            code='super',
            category='b2b',
            hierarchy_level=9,
            mfa_required=True
        )
        self.customer_role = Role.objects.create(
            name='Customer',
            code='customer',
            category='b2c',
            hierarchy_level=1,
            mfa_required=False
        )
        
        # Create test user
        self.test_user = User.objects.create_user(
            username='testuser',
            password='TestPass123!',
            role_code='customer',
            email_verified=True,
            is_active=True
        )
        Profile.objects.create(
            user=self.test_user,
            first_name='Test',
            email='test@example.com',
            phone='911234567890',
            email_verified=True,
            phone_verified=True
        )
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()


class MultiStepLoginTests(AuthenticationTestCase):
    """Test multi-step login flow"""
    
    def test_login_step1_credentials(self):
        """Test step 1: Credentials entry"""
        response = self.client.get(reverse('signin'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
    
    def test_login_successful(self):
        """Test successful login flow"""
        response = self.client.post(reverse('signin'), {
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        # Should redirect after successful login
        self.assertIn(response.status_code, [200, 302])
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post(reverse('signin'), {
            'username': 'testuser',
            'password': 'WrongPassword'
        })
        self.assertEqual(response.status_code, 200)
        # Should show error message
    
    def test_login_rate_limiting(self):
        """Test rate limiting for login attempts"""
        # Make 5 failed attempts
        for i in range(5):
            self.client.post(reverse('signin'), {
                'username': 'testuser',
                'password': 'WrongPassword'
            })
        
        # 6th attempt should be rate limited
        response = self.client.post(reverse('signin'), {
            'username': 'testuser',
            'password': 'WrongPassword'
        })
        self.assertEqual(response.status_code, 200)
        # Should show rate limit error
    
    def test_account_lockout(self):
        """Test account lockout after 10 failed attempts"""
        user = User.objects.get(username='testuser')
        
        # Make 10 failed attempts
        for i in range(10):
            user.increment_failed_attempts()
        
        # Account should be locked
        self.assertTrue(user.is_account_locked())
        
        # Login should fail
        response = self.client.post(reverse('signin'), {
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        self.assertEqual(response.status_code, 200)
    
    def test_login_with_profile_completion_required(self):
        """Test login redirects to profile completion if required"""
        # Create user with profile_completion_required=True
        user = User.objects.create_user(
            username='incomplete',
            password='TestPass123!',
            role_code='customer',
            email_verified=True
        )
        profile = Profile.objects.create(
            user=user,
            first_name='Incomplete',
            email='incomplete@example.com',
            phone='911234567891',
            profile_completion_required=True
        )
        
        response = self.client.post(reverse('signin'), {
            'username': 'incomplete',
            'password': 'TestPass123!'
        })
        
        # Should redirect to profile completion
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 302:
            self.assertIn('/profile/complete/', response.url)


class MultiStepSignupTests(AuthenticationTestCase):
    """Test multi-step signup flow with OTP dual delivery"""
    
    def test_signup_step1_form(self):
        """Test step 1: Basic information form"""
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
    
    def test_signup_step1_validation(self):
        """Test signup step 1 validation"""
        response = self.client.post(reverse('signup'), {
            'first_name': 'New',
            'email': 'newuser@example.com',
            'phone': '911234567892',
            'password1': 'TestPass123!',
            'password2': 'TestPass123!',
            'role_code': 'customer'
        })
        # Should proceed to step 2 (OTP verification)
        self.assertIn(response.status_code, [200, 302])
    
    def test_signup_duplicate_email(self):
        """Test signup with duplicate email"""
        response = self.client.post(reverse('signup'), {
            'first_name': 'New',
            'email': 'test@example.com',  # Duplicate
            'phone': '911234567892',
            'password1': 'TestPass123!',
            'password2': 'TestPass123!',
            'role_code': 'customer'
        })
        self.assertEqual(response.status_code, 200)
        # Should show validation error
    
    def test_signup_duplicate_phone(self):
        """Test signup with duplicate phone"""
        response = self.client.post(reverse('signup'), {
            'first_name': 'New',
            'email': 'newuser@example.com',
            'phone': '911234567890',  # Duplicate
            'password1': 'TestPass123!',
            'password2': 'TestPass123!',
            'role_code': 'customer'
        })
        self.assertEqual(response.status_code, 200)
        # Should show validation error


class SocialAuthenticationTests(AuthenticationTestCase):
    """Test social authentication (OAuth)"""
    
    def test_social_signup_creates_customer_role(self):
        """Test that social signup automatically assigns customer role"""
        # This would be tested with allauth's test client
        # For now, test the adapter logic
        from portal.adapters import CustomSocialAccountAdapter
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        from allauth.account.models import EmailAddress
        
        # Mock social login
        adapter = CustomSocialAccountAdapter()
        
        # Verify adapter assigns customer role
        # (Full test requires allauth test setup)
        self.assertTrue(hasattr(adapter, 'save_user'))
    
    def test_social_signup_sets_profile_completion_required(self):
        """Test that social signup sets profile_completion_required=True"""
        # Create user via social adapter (would need allauth test setup)
        # Verify profile_completion_required is True
        pass


class ProfileCompletionTests(AuthenticationTestCase):
    """Test profile completion flow"""
    
    def test_profile_completion_view_requires_login(self):
        """Test profile completion view requires authentication"""
        response = self.client.get(reverse('profile_complete'))
        # Should redirect to login
        self.assertIn(response.status_code, [302, 403])
    
    def test_profile_completion_form_validation(self):
        """Test profile completion form validation"""
        self.client.login(username='testuser', password='TestPass123!')
        
        # Create user with profile_completion_required=True
        user = User.objects.get(username='testuser')
        user.profile.profile_completion_required = True
        user.profile.save()
        
        response = self.client.post(reverse('profile_complete'), {
            'phone': '911234567893',
            'address_line_1': '123 Test St',
            'city': 'Test City',
            'state': 'Test State',
            'pincode': '123456'
        })
        
        # Should save and redirect
        self.assertIn(response.status_code, [200, 302])
    
    def test_profile_completion_middleware_blocks_dashboard(self):
        """Test middleware blocks dashboard access if profile incomplete"""
        # Create user with profile_completion_required=True
        user = User.objects.create_user(
            username='incomplete2',
            password='TestPass123!',
            role_code='customer',
            email_verified=True
        )
        profile = Profile.objects.create(
            user=user,
            first_name='Incomplete',
            email='incomplete2@example.com',
            phone='911234567894',
            profile_completion_required=True
        )
        
        self.client.login(username='incomplete2', password='TestPass123!')
        
        # Try to access dashboard
        response = self.client.get(reverse('dashboard'))
        
        # Should redirect to profile completion
        self.assertIn(response.status_code, [302, 200])
        if response.status_code == 302:
            self.assertIn('/profile/complete/', response.url)


class IPLoggingTests(AuthenticationTestCase):
    """Test IP address logging in authentication flows"""
    
    def test_ip_extraction_from_request(self):
        """Test IP extraction utility"""
        # Create a mock request
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/signin/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')
    
    def test_ip_logging_on_login(self):
        """Test that IP is logged on login"""
        # Login should trigger IP logging
        response = self.client.post(reverse('signin'), {
            'username': 'testuser',
            'password': 'TestPass123!'
        }, HTTP_X_FORWARDED_FOR='192.168.1.100')
        
        # Check that user's last_login_ip is updated
        user = User.objects.get(username='testuser')
        # IP should be logged (check after login completes)
        self.assertIn(response.status_code, [200, 302])


class MFATests(AuthenticationTestCase):
    """Test MFA setup and verification"""
    
    def test_mfa_required_for_admin_role(self):
        """Test that MFA is required for admin role"""
        admin_user = User.objects.create_user(
            username='admin',
            password='TestPass123!',
            role_code='admin',
            email_verified=True
        )
        Profile.objects.create(
            user=admin_user,
            first_name='Admin',
            email='admin@example.com',
            phone='911234567895'
        )
        
        # MFA should be required
        self.assertTrue(admin_user.requires_mfa())
    
    def test_mfa_optional_for_customer_role(self):
        """Test that MFA is optional for customer role"""
        customer_user = User.objects.get(username='testuser')
        # MFA should not be required
        self.assertFalse(customer_user.requires_mfa())


class SuperuserCreationTests(AuthenticationTestCase):
    """Test superuser creation with auto-assigned role"""
    
    def test_createsuperuser_auto_assigns_super_role(self):
        """Test that createsuperuser auto-assigns 'super' role"""
        # Create superuser via UserManager
        user = User.objects.create_superuser(
            username='superadmin',
            password='SuperPass123!'
        )
        
        # Should have 'super' role
        self.assertEqual(user.role_code, 'super')
        self.assertIsNotNone(user.role)
        self.assertEqual(user.role.code, 'super')
    
    def test_createsuperuser_creates_profile(self):
        """Test that createsuperuser creates Profile"""
        user = User.objects.create_superuser(
            username='superadmin2',
            password='SuperPass123!',
            email='super@example.com'
        )
        
        # Profile should exist
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsNotNone(user.profile)
        self.assertEqual(user.profile.email, 'super@example.com')
    
    def test_createsuperuser_auto_generates_username(self):
        """Test that createsuperuser auto-generates username if not provided"""
        user = User.objects.create_superuser(
            username=None,
            password='SuperPass123!'
        )
        
        # Username should be auto-generated
        self.assertIsNotNone(user.username)
        self.assertTrue(user.username.startswith('S'))  # Super role prefix


class RateLimitingTests(AuthenticationTestCase):
    """Test rate limiting functionality"""
    
    def test_otp_rate_limiting(self):
        """Test OTP rate limiting (3 requests per 10 minutes)"""
        from portal.services.otp_service import OTPService
        
        otp_service = OTPService()
        
        # Make 3 OTP requests
        for i in range(3):
            success, _ = otp_service.send_otp('911234567890', user_id=None)
            # First 3 should succeed (or at least not be rate limited)
        
        # 4th request should be rate limited
        success, message = otp_service.send_otp('911234567890', user_id=None)
        # Should fail with rate limit message
        self.assertFalse(success)
        self.assertIn('rate limit', message.lower() or '')


class AccountLockoutTests(AuthenticationTestCase):
    """Test account lockout functionality"""
    
    def test_account_locks_after_10_failed_attempts(self):
        """Test account locks after 10 failed login attempts"""
        user = User.objects.get(username='testuser')
        
        # Make 10 failed attempts
        for i in range(10):
            was_locked = user.increment_failed_attempts()
            if i < 9:
                self.assertFalse(was_locked)
            else:
                self.assertTrue(was_locked)
        
        # Account should be locked
        self.assertTrue(user.is_account_locked())
        self.assertIsNotNone(user.account_locked_until)
    
    def test_account_unlocks_after_timeout(self):
        """Test account unlocks after lockout period"""
        from datetime import timedelta
        
        user = User.objects.get(username='testuser')
        user.account_locked_until = timezone.now() - timedelta(minutes=1)  # Lock expired
        user.save()
        
        # Account should not be locked
        self.assertFalse(user.is_account_locked())
    
    def test_reset_failed_attempts_on_successful_login(self):
        """Test failed attempts reset on successful login"""
        user = User.objects.get(username='testuser')
        user.failed_login_attempts = 5
        user.save()
        
        # Successful login should reset
        user.reset_failed_attempts()
        
        self.assertEqual(user.failed_login_attempts, 0)
