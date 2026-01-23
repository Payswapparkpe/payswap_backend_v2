"""
TDD tests for UserManager customization
Tests: Auto-role assignment, username generation, Profile creation
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from portal.models import Profile, Role
from portal.utils.user_utils import generate_username, get_role_prefix


User = get_user_model()


class UserManagerTests(TestCase):
    """Test UserManager customizations"""
    
    def setUp(self):
        """Set up test data"""
        # Create roles
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
    
    def test_create_superuser_auto_assigns_super_role(self):
        """Test create_superuser auto-assigns 'super' role"""
        user = User.objects.create_superuser(
            username='superadmin',
            password='SuperPass123!'
        )
        
        # Should have 'super' role
        self.assertEqual(user.role_code, 'super')
        self.assertIsNotNone(user.role)
        self.assertEqual(user.role.code, 'super')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
    
    def test_create_superuser_creates_profile(self):
        """Test create_superuser automatically creates Profile"""
        user = User.objects.create_superuser(
            username='superadmin2',
            password='SuperPass123!',
            email='super@example.com'
        )
        
        # Profile should exist
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsNotNone(user.profile)
        self.assertEqual(user.profile.email, 'super@example.com')
        self.assertEqual(user.profile.user, user)
    
    def test_create_superuser_auto_generates_username(self):
        """Test create_superuser auto-generates username if not provided"""
        user = User.objects.create_superuser(
            username=None,
            password='SuperPass123!'
        )
        
        # Username should be auto-generated
        self.assertIsNotNone(user.username)
        self.assertTrue(len(user.username) > 0)
        # Should start with 'S' for super role
        self.assertTrue(user.username.startswith('S'))
    
    def test_create_user_requires_role(self):
        """Test create_user requires role_code"""
        with self.assertRaises(Exception):
            User.objects.create_user(
                username='testuser',
                password='TestPass123!'
                # Missing role_code
            )
    
    def test_create_user_auto_generates_username(self):
        """Test create_user auto-generates username if not provided"""
        user = User.objects.create_user(
            username=None,
            password='TestPass123!',
            role_code='customer'
        )
        
        # Username should be auto-generated
        self.assertIsNotNone(user.username)
        self.assertTrue(len(user.username) > 0)
        # Should start with 'C' for customer role
        self.assertTrue(user.username.startswith('C'))
    
    def test_create_user_sets_role_object(self):
        """Test create_user sets Role object"""
        user = User.objects.create_user(
            username='testuser',
            password='TestPass123!',
            role_code='customer'
        )
        
        # Role object should be set
        self.assertIsNotNone(user.role)
        self.assertEqual(user.role.code, 'customer')
        self.assertEqual(user.role_code, 'customer')
