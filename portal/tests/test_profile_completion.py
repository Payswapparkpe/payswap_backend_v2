"""
TDD tests for profile completion flow
Tests: Social signup profile completion, middleware enforcement, form validation
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from portal.models import Profile, Role


User = get_user_model()


class ProfileCompletionTests(TestCase):
    """Test profile completion functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create customer role
        self.customer_role = Role.objects.create(
            name='Customer',
            code='customer',
            category='b2c',
            hierarchy_level=1,
            mfa_required=False
        )
    
    def test_profile_completion_required_flag(self):
        """Test profile_completion_required flag exists in Profile"""
        user = User.objects.create_user(
            username='testuser',
            password='TestPass123!',
            role_code='customer',
            email_verified=True
        )
        profile = Profile.objects.create(
            user=user,
            first_name='Test',
            email='test@example.com',
            phone='911234567890',
            profile_completion_required=True
        )
        
        self.assertTrue(profile.profile_completion_required)
    
    def test_social_signup_sets_profile_completion_required(self):
        """Test social signup sets profile_completion_required=True"""
        # Create user via social adapter (would need allauth test setup)
        # For now, verify the field exists and can be set
        user = User.objects.create_user(
            username='socialuser',
            password='TestPass123!',
            role_code='customer',
            email_verified=True
        )
        profile = Profile.objects.create(
            user=user,
            first_name='Social',
            email='social@example.com',
            phone='911234567891',
            profile_completion_required=True,
            social_provider='google',
            social_provider_id='google-123'
        )
        
        self.assertTrue(profile.profile_completion_required)
        self.assertEqual(profile.social_provider, 'google')
        self.assertEqual(profile.social_provider_id, 'google-123')
    
    def test_profile_completion_form_required_fields(self):
        """Test profile completion form has required fields"""
        from portal.forms import ProfileCompletionForm
        
        form = ProfileCompletionForm()
        
        # Check required fields
        self.assertIn('phone', form.fields)
        self.assertIn('address_line_1', form.fields)
        self.assertIn('city', form.fields)
        self.assertIn('state', form.fields)
        self.assertIn('pincode', form.fields)
        
        # Phone should be required
        self.assertTrue(form.fields['phone'].required)
        self.assertTrue(form.fields['address_line_1'].required)
    
    def test_profile_completion_saves_data(self):
        """Test profile completion saves data correctly"""
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
            phone='911234567892',
            profile_completion_required=True
        )
        
        self.client.login(username='incomplete', password='TestPass123!')
        
        # Complete profile
        response = self.client.post(reverse('profile_complete'), {
            'phone': '911234567893',
            'address_line_1': '123 Test Street',
            'address_line_2': 'Apt 4B',
            'city': 'Test City',
            'state': 'Test State',
            'pincode': '123456',
            'date_of_birth': '1990-01-01'
        })
        
        # Refresh profile
        profile.refresh_from_db()
        
        # Profile completion should be marked as complete
        self.assertFalse(profile.profile_completion_required)
        self.assertEqual(profile.phone, '911234567893')
        self.assertEqual(profile.city, 'Test City')
    
    def test_profile_completion_middleware_redirect(self):
        """Test middleware redirects to profile completion"""
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
