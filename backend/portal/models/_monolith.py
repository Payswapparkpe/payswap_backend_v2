"""
Portal Models - User Management, KYC, Wallet
"""
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission, UserManager as BaseUserManager
from simple_history.models import HistoricalRecords
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from portal.utils.user_utils import generate_username, get_role_prefix, is_mfa_required_role
from portal.utils.encryption import encrypt_data, decrypt_data
from portal.utils.validators import validate_phone_number, validate_pan_number, validate_aadhaar_number
from portal.utils.logging_helper import get_logger

logger = get_logger('portal.models')


class UserManager(BaseUserManager):
    """Custom UserManager that handles auto-generated usernames"""
    
    def _create_user_object(self, username, email, password, **extra_fields):
        """
        Override to handle email field
        Email field exists in User model (nullable) for Django compatibility
        But actual email is stored in Profile model
        """
        # Keep email in extra_fields if provided (Django's createsuperuser may pass it)
        # It will be stored in User.email (nullable field) and later synced to Profile
        user = self.model(username=username, **extra_fields)
        if email:
            user.email = email  # Store in User.email field (for Django compatibility)
        user.set_password(password)
        return user
    
    def create_user(self, username=None, email=None, password=None, **extra_fields):
        """Create user with auto-generated username if not provided"""
        role_code = extra_fields.get('role_code')
        if not role_code:
            raise ValidationError({'role_code': 'Role is required. All users must have a role.'})
        
        # Generate username if not provided
        if not username:
            role_prefix = get_role_prefix(role_code)
            username = generate_username(role_prefix)
        
        # Ensure Role object is set
        from portal.models import Role
        try:
            role_obj = Role.objects.get(code=role_code)
            extra_fields['role'] = role_obj
        except Role.DoesNotExist:
            raise ValidationError({
                'role_code': f'Role with code "{role_code}" does not exist. Please run "python manage.py setup_roles" first.'
            })
        
        # Call parent create_user (email will be ignored)
        return super().create_user(username, password=password, **extra_fields)
    
    def create_superuser(self, username=None, password=None, **extra_fields):
        """
        Create superuser with auto-generated username and auto-assigned "super_admin" role
        Uses Django's built-in createsuperuser command flow
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        # Auto-assign "super_admin" role for superusers (unless explicitly overridden)
        if 'role_code' not in extra_fields:
            extra_fields['role_code'] = 'super_admin'
        
        # Auto-verify email for superusers
        extra_fields.setdefault('email_verified', True)
        
        # Create user (this will auto-generate username if not provided)
        user = self.create_user(username, password, **extra_fields)
        
        # Create Profile if it doesn't exist (mandatory OneToOne)
        # Profile will be created with minimal data - can be updated later via admin or profile page
        if not hasattr(user, 'profile') or not user.profile:
            from portal.models import Profile
            import random
            # Get email from user.email (set by Django's createsuperuser if provided)
            # Or use a default placeholder that must be updated
            email = user.email if user.email else f'{user.username}@payswap.local'
            # Use first_name from user if available, otherwise use username
            first_name = user.first_name if user.first_name else user.username
            # Generate unique placeholder phone (91 + 10 random digits)
            # Keep trying until we find a unique one
            phone = None
            max_attempts = 10
            for _ in range(max_attempts):
                random_digits = ''.join([str(random.randint(0, 9)) for _ in range(10)])
                candidate_phone = f'91{random_digits}'
                if not Profile.objects.filter(phone=candidate_phone).exists():
                    phone = candidate_phone
                    break
            # Fallback if all attempts fail (very unlikely)
            if not phone:
                phone = f'91{user.id:010d}'  # Use user ID padded to 10 digits
            Profile.objects.create(
                user=user,
                first_name=first_name,
                email=email,
                phone=phone,  # Unique placeholder - MUST be updated via profile page
                type='individual',
                email_verified=user.email_verified if user.email else False,
                phone_verified=False,  # Phone needs to be updated and verified
            )
        
        return user


class Profile(models.Model):
    """Profile model - Mandatory OneToOne with User, contains all user details"""
    
    PROFILE_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
        ('corporate', 'Corporate'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]
    
    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
    ]
    
    # ============================================================================
    # RELATIONSHIP
    # ============================================================================
    user = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='profile',
        null=False,
        blank=False,
        help_text="Mandatory profile for every user"
    )
    
    # ============================================================================
    # PERSONAL DETAILS
    # ============================================================================
    first_name = models.CharField(
        max_length=150,
        blank=False,
        help_text="Required. User's first name."
    )
    middle_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    
    @property
    def full_name(self):
        """Get full name"""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        if self.last_name:
            parts.append(self.last_name)
        return ' '.join(parts)
    
    # Profile Photo
    profile_photo = models.ImageField(
        upload_to='profiles/photos/',
        blank=True,
        null=True,
        help_text="User profile photo"
    )
    
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
        null=True
    )
    marital_status = models.CharField(
        max_length=20,
        choices=MARITAL_STATUS_CHOICES,
        blank=True,
        null=True
    )
    
    # ============================================================================
    # DEMOGRAPHIC DETAILS
    # ============================================================================
    nationality = models.CharField(max_length=100, blank=True, null=True, default='Indian')
    country_of_residence = models.CharField(max_length=100, blank=True, null=True, default='India')
    state = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    address_line_1 = models.TextField(blank=True, null=True)
    address_line_2 = models.TextField(blank=True, null=True)
    
    @property
    def full_address(self):
        """Get full address"""
        parts = []
        if self.address_line_1:
            parts.append(self.address_line_1)
        if self.address_line_2:
            parts.append(self.address_line_2)
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.pincode:
            parts.append(self.pincode)
        if self.country_of_residence:
            parts.append(self.country_of_residence)
        return ', '.join(parts)
    
    # ============================================================================
    # CONTACT DETAILS (Unique and Required)
    # ============================================================================
    email = models.EmailField(
        unique=True,
        blank=False,
        help_text="Required. User's email address. Must be unique."
    )
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        unique=True,
        blank=False,
        help_text="Required. User's mobile number. Must be unique."
    )
    alternate_phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        blank=True,
        null=True
    )
    
    # ============================================================================
    # BANKING DETAILS
    # ============================================================================
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_holder_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=11, blank=True, null=True)
    branch_name = models.CharField(max_length=255, blank=True, null=True)
    account_type = models.CharField(
        max_length=20,
        choices=[('savings', 'Savings'), ('current', 'Current')],
        blank=True,
        null=True
    )
    # Encrypted banking details
    encrypted_banking_details = models.TextField(blank=True, null=True)
    
    def set_encrypted_banking_details(self, details: dict) -> None:
        """Set encrypted banking details"""
        import json
        if details:
            self.encrypted_banking_details = encrypt_data(json.dumps(details))
        else:
            self.encrypted_banking_details = None
    
    def get_decrypted_banking_details(self) -> dict:
        """Get decrypted banking details"""
        import json
        if self.encrypted_banking_details:
            try:
                return json.loads(decrypt_data(self.encrypted_banking_details))
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                logger.warning(
                    'Failed to decrypt banking details for profile pk=%s: %s',
                    self.pk,
                    e,
                    exc_info=True
                )
                return {}
        return {}
    
    # ============================================================================
    # TAXATION DETAILS
    # ============================================================================
    pan_number = models.CharField(
        max_length=10,
        validators=[validate_pan_number],
        blank=True,
        null=True,
        help_text="PAN number (10 characters)"
    )
    aadhaar_number = models.CharField(
        max_length=12,
        validators=[validate_aadhaar_number],
        blank=True,
        null=True,
        help_text="Aadhaar number (12 digits)"
    )
    gst_number = models.CharField(max_length=15, blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True)  # Other tax IDs
    
    # ============================================================================
    # BUSINESS DETAILS (for business profiles)
    # ============================================================================
    type = models.CharField(
        max_length=20,
        choices=PROFILE_TYPE_CHOICES,
        default='individual'
    )
    business_name = models.CharField(max_length=255, blank=True, null=True)
    business_registration_number = models.CharField(max_length=100, blank=True, null=True)
    business_type = models.CharField(max_length=100, blank=True, null=True)  # Pvt Ltd, LLP, etc.
    
    # ============================================================================
    # SETTINGS & PREFERENCES
    # ============================================================================
    language_preference = models.CharField(max_length=10, default='en', blank=True)
    timezone = models.CharField(max_length=50, default='Asia/Kolkata', blank=True)
    currency_preference = models.CharField(max_length=3, default='INR', blank=True)
    
    # Notification preferences (stored as JSON)
    notification_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Notification preferences (email, SMS, push, etc.)"
    )
    
    # General settings (stored as JSON)
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="General user settings and preferences"
    )
    
    # ============================================================================
    # ACCOUNT SECURITY
    # ============================================================================
    # Security questions (encrypted)
    security_question_1 = models.TextField(blank=True, null=True)  # Encrypted
    security_answer_1 = models.TextField(blank=True, null=True)  # Encrypted
    security_question_2 = models.TextField(blank=True, null=True)  # Encrypted
    security_answer_2 = models.TextField(blank=True, null=True)  # Encrypted
    
    # Two-factor authentication backup codes (encrypted)
    backup_codes = models.TextField(blank=True, null=True)  # Encrypted JSON array
    
    # Account recovery email
    recovery_email = models.EmailField(blank=True, null=True)
    
    # Last password change date
    last_password_change = models.DateTimeField(null=True, blank=True)
    
    # ============================================================================
    # METADATA & STATUS
    # ============================================================================
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified = models.BooleanField(default=False)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Profile completion flag (for social signup users)
    profile_completion_required = models.BooleanField(
        default=False,
        help_text="True if user must complete profile details (e.g., after social signup)"
    )
    
    # Social authentication provider information
    social_provider = models.CharField(
        max_length=20,
        choices=[
            ('google', 'Google'),
            ('facebook', 'Facebook'),
            ('apple', 'Apple')
        ],
        blank=True,
        null=True,
        help_text="Social provider used for signup/login"
    )
    social_provider_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="User ID from social provider"
    )
    
    # Audit fields
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_profiles'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_profiles'
    )
    
    # Postman sync: API key for fetching collections from Postman (Postman → Portal sync)
    postman_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Postman API key for syncing collections to this portal (optional)"
    )

    # ParkPe Connect: block/warn for abuse (call/chat)
    connect_blocked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, user is blocked from Connect (call/chat) until this time"
    )
    connect_warning_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of Connect warnings issued (admin can increment)"
    )
    
    class Meta:
        db_table = 'portal_profile'
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.full_name} ({self.email})"
    
    def clean(self):
        """Validate profile data"""
        # Email and phone are required and unique (enforced at DB level)
        if not self.email or not self.email.strip():
            raise ValidationError({'email': 'Email is required.'})
        if not self.phone or not self.phone.strip():
            raise ValidationError({'phone': 'Mobile number is required.'})
        if not self.first_name or not self.first_name.strip():
            raise ValidationError({'first_name': 'First name is required.'})


class Role(models.Model):
    """Role model for user roles"""
    
    CATEGORY_CHOICES = [
        ('b2b', 'B2B'),
        ('b2c', 'B2C'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True)  # admin, employee, super, etc.
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    hierarchy_level = models.IntegerField(default=0)  # Higher number = higher hierarchy
    default_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name='roles'
    )
    mfa_required = models.BooleanField(default=False)  # MFA enforcement flag
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portal_role'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        ordering = ['-hierarchy_level', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def save(self, *args, **kwargs):
        # Auto-set MFA required based on role code
        if not self.mfa_required:
            self.mfa_required = is_mfa_required_role(self.code)
        super().save(*args, **kwargs)


class User(AbstractUser):
    """Custom User model - Only credentials and login details"""
    
    objects = UserManager()
    
    # REQUIRED_FIELDS: Django's createsuperuser will prompt for these fields
    # We keep it empty since email is stored in Profile, not User model
    # Django's default createsuperuser will still work because email field exists (nullable)
    REQUIRED_FIELDS = []  # Username and password are handled by AbstractUser
    
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('employee', 'Employee'),
        ('super_distributor', 'Super Distributor'),
        ('distributor', 'Distributor'),
        ('retailer', 'Retailer'),
        ('customer', 'Customer'),
        ('fleet_admin', 'Fleet Admin'),
        ('fleet_manager', 'Fleet Manager'),
        ('fleet_operator', 'Fleet Operator'),
        ('fleet_dispatcher', 'Fleet Dispatcher'),
        ('parking_owner', 'Parking Owner'),
        ('parking_manager', 'Parking Manager'),
        ('parking_attendant', 'Parking Attendant'),
    ]
    
    KYC_STATUS_CHOICES = [
        ('not_required', 'Not Required'),
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    MFA_METHOD_CHOICES = [
        ('otp', 'OTP (SMS)'),
        ('authenticator', 'Authenticator App'),
    ]
    
    # ============================================================================
    # CREDENTIALS (Auto-generated username, unique)
    # ============================================================================
    username = models.CharField(
        max_length=15,  # Format: A00XXXXXXXX (1 char + 2 zeros + 8 alphanumeric = 11 chars)
        unique=True,
        help_text="Auto-generated cryptographically secure username"
    )
    
    # Override AbstractUser fields to be nullable (data is in Profile)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    # Email field: Keep as nullable field for Django compatibility, but use property to read from Profile
    email = models.EmailField(blank=True, null=True, help_text="Email is stored in Profile model")
    
    # Password is inherited from AbstractUser
    
    # ============================================================================
    # ROLE & AUTHORIZATION
    # ============================================================================
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    
    role_code = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        blank=False,
        null=False,
        help_text="User role code (required)"
    )
    
    # ============================================================================
    # LOGIN & SESSION DETAILS
    # ============================================================================
    # last_login is inherited from AbstractUser
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_user_agent = models.TextField(blank=True, null=True)
    login_count = models.IntegerField(default=0)
    
    # Account lockout for failed login attempts
    failed_login_attempts = models.IntegerField(default=0, help_text="Number of consecutive failed login attempts")
    account_locked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Account locked until this timestamp (30 minutes after 10 failed attempts)"
    )
    
    # ============================================================================
    # EMAIL VERIFICATION (moved from profile for login checks)
    # ============================================================================
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    
    # ============================================================================
    # KYC STATUS (for login checks)
    # ============================================================================
    kyc_completed = models.BooleanField(default=False)
    kyc_status = models.CharField(
        max_length=20,
        choices=KYC_STATUS_CHOICES,
        default='not_required'
    )
    
    # ============================================================================
    # MFA (Multi-Factor Authentication)
    # ============================================================================
    mfa_enabled = models.BooleanField(default=False)
    mfa_configured = models.BooleanField(default=False)
    mfa_method = models.CharField(
        max_length=20,
        choices=MFA_METHOD_CHOICES,
        blank=True,
        null=True
    )
    totp_secret = models.CharField(max_length=200, blank=True, null=True)  # Encrypted TOTP secret (Fernet encryption produces ~140 chars)
    
    # ============================================================================
    # SESSION LOCK / PIN UNLOCK (Secondary re-unlock only; OTP/2FA is primary auth)
    # ============================================================================
    pin_hash = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text='Hashed 4-digit PIN (Django make_password). Never store plaintext.'
    )
    pin_set_at = models.DateTimeField(null=True, blank=True, help_text='When PIN was last set')
    pin_failed_attempts = models.IntegerField(
        default=0,
        help_text='Consecutive failed PIN attempts; lock after 5'
    )
    pin_locked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='PIN unlock blocked until this time (30 min after 5 failures)'
    )
    last_full_auth_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last successful OTP/2FA login; PIN unlock allowed only within window (e.g. 24h)'
    )
    
    # ============================================================================
    # ACCOUNT STATUS
    # ============================================================================
    # is_active, is_staff, is_superuser are inherited from AbstractUser
    
    # ============================================================================
    # AUDIT & TRACKING
    # ============================================================================
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portal_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.get_role_code_display()})"
    
    def clean(self):
        """Validate required fields"""
        # Role is mandatory
        if not self.role_code:
            raise ValidationError({'role_code': 'Role is required. Please select a role for the user.'})
        
        # Validate role_code is a valid choice
        valid_role_codes = [choice[0] for choice in self.ROLE_CHOICES]
        if self.role_code not in valid_role_codes:
            raise ValidationError({'role_code': f'Invalid role code. Must be one of: {", ".join(valid_role_codes)}'})
        
        # Ensure Role object exists for this role_code
        if self.role_code:
            try:
                role_obj = Role.objects.get(code=self.role_code)
                if not self.role:
                    self.role = role_obj
            except Role.DoesNotExist:
                raise ValidationError({
                    'role_code': f'Role with code "{self.role_code}" does not exist. Please run "python manage.py setup_roles" first.'
                })
        
        # Auto-generate username if not set
        if not self.username and self.role_code:
            role_prefix = get_role_prefix(self.role_code)
            self.username = generate_username(role_prefix)
    
    def save(self, *args, **kwargs):
        # Validate role_code is set (mandatory)
        if not self.role_code:
            raise ValidationError({'role_code': 'Role is required. All users must have a role.'})
        
        # Auto-generate username if not set
        if not self.username and self.role_code:
            role_prefix = get_role_prefix(self.role_code)
            self.username = generate_username(role_prefix)
        
        # Ensure Role object exists and is set
        if self.role_code:
            try:
                role_obj = Role.objects.get(code=self.role_code)
                self.role = role_obj
            except Role.DoesNotExist:
                raise ValidationError({
                    'role_code': f'Role with code "{self.role_code}" does not exist. Please run "python manage.py setup_roles" first.'
                })
        
        # Save first to ensure user exists
        super().save(*args, **kwargs)
        
        # Sync to Django Groups after save (role is guaranteed to exist)
        if self.role:
            from portal.utils.role_utils import sync_user_to_groups
            sync_user_to_groups(self, self.role)
    
    
    def requires_mfa(self) -> bool:
        """Check if user's role requires MFA"""
        if self.role:
            return self.role.mfa_required
        return is_mfa_required_role(self.role_code)
    
    def can_login(self) -> bool:
        """Check if user can login (all requirements met)"""
        if not self.is_active:
            return False
        if not self.email_verified:
            return False
        # Check if account is locked
        if self.is_account_locked():
            return False
        if self.requires_mfa() and not self.mfa_configured:
            return False
        # Check KYC if required for role
        kyc_required_roles = ['customer', 'distributor', 'retailer']
        if self.role_code in kyc_required_roles and not self.kyc_completed:
            return False
        return True
    
    def is_account_locked(self) -> bool:
        """Check if account is currently locked"""
        if self.account_locked_until:
            from django.utils import timezone
            if timezone.now() < self.account_locked_until:
                return True
            else:
                # Lock expired, unlock account
                self.unlock_account()
        return False
    
    def lock_account(self, lockout_duration_minutes: int = 30):
        """
        Lock account for specified duration
        
        Args:
            lockout_duration_minutes: Duration in minutes (default: 30)
        """
        from django.utils import timezone
        from datetime import timedelta
        self.account_locked_until = timezone.now() + timedelta(minutes=lockout_duration_minutes)
        self.save(update_fields=['account_locked_until'])
    
    def unlock_account(self):
        """Unlock account and reset failed attempts"""
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['account_locked_until', 'failed_login_attempts'])
    
    def increment_failed_attempts(self, max_attempts: int = 10):
        """
        Increment failed login attempts and lock if threshold reached
        
        Args:
            max_attempts: Maximum attempts before lockout (default: 10)
        
        Returns:
            True if account was locked, False otherwise
        """
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.lock_account()
            return True
        self.save(update_fields=['failed_login_attempts'])
        return False
    
    def reset_failed_attempts(self):
        """Reset failed login attempts (called on successful login)"""
        if self.failed_login_attempts > 0:
            self.failed_login_attempts = 0
            self.save(update_fields=['failed_login_attempts'])
    
    def get_encrypted_totp_secret(self) -> str:
        """Get decrypted TOTP secret"""
        if self.totp_secret:
            try:
                return decrypt_data(self.totp_secret)
            except (ValueError, TypeError) as e:
                logger.warning(
                    'Failed to decrypt TOTP secret for user pk=%s: %s',
                    self.pk,
                    e,
                    exc_info=True
                )
                return ""
        return ""
    
    def set_encrypted_totp_secret(self, secret: str) -> None:
        """Set encrypted TOTP secret"""
        if secret:
            self.totp_secret = encrypt_data(secret)
        else:
            self.totp_secret = None
    
    # Convenience methods to access profile data
    # Note: email and first_name are database fields, not properties
    # They are synced with profile but stored in User model for Django compatibility
    
    @property
    def phone(self):
        """Get phone from profile"""
        return self.profile.phone if hasattr(self, 'profile') and self.profile else None
    
    @property
    def full_name(self):
        """Get full_name from profile"""
        return self.profile.full_name if hasattr(self, 'profile') and self.profile else None


class KYC(models.Model):
    """KYC (Know Your Customer) model"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    DOCUMENT_TYPE_CHOICES = [
        ('aadhaar', 'Aadhaar'),
        ('pan', 'PAN'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('voter_id', 'Voter ID'),
    ]
    
    VERIFICATION_VENDOR_CHOICES = [
        ('cashfree', 'Cashfree'),
        ('invincible_ocean', 'Invincible Ocean'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='kyc'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES
    )
    
    document_number = models.CharField(max_length=50)
    
    # S3 URLs for document files
    document_files = models.JSONField(
        default=list,
        help_text="List of S3 URLs for document files"
    )
    document_file_keys = models.JSONField(
        default=list,
        blank=True,
        help_text="List of private S3 object keys for secure document access"
    )
    
    # Verification vendor info
    verification_vendor = models.CharField(
        max_length=20,
        choices=VERIFICATION_VENDOR_CHOICES,
        blank=True,
        null=True
    )
    
    verification_id = models.CharField(max_length=255, blank=True, null=True)
    verification_response = models.JSONField(default=dict, blank=True, null=True)
    
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_kycs'
    )
    
    rejection_reason = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    history = HistoricalRecords(
        inherit=False,
        excluded_fields=['created_at', 'updated_at'],
        user_model=settings.AUTH_USER_MODEL,
    )

    class Meta:
        db_table = 'portal_kyc'
        verbose_name = 'KYC'
        verbose_name_plural = 'KYCs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"KYC for {self.user.username} - {self.status}"
    
    def approve(self, verified_by: User) -> None:
        """Approve KYC"""
        self.status = 'approved'
        self.verified_at = timezone.now()
        self.verified_by = verified_by
        self.user.kyc_completed = True
        self.user.kyc_status = 'approved'
        self.user.save()
        self.save()
    
    def reject(self, verified_by: User, reason: str) -> None:
        """Reject KYC"""
        self.status = 'rejected'
        self.verified_at = timezone.now()
        self.verified_by = verified_by
        self.rejection_reason = reason
        self.user.kyc_completed = False
        self.user.kyc_status = 'rejected'
        self.user.save()
        self.save()


class Wallet(models.Model):
    """Wallet model for user funds"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('frozen', 'Frozen'),
        ('closed', 'Closed'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    
    balance = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00
    )
    
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Encrypted seed phrase
    encrypted_seed_phrase = models.TextField(blank=True, null=True)
    
    wallet_address = models.CharField(max_length=255, unique=True, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portal_wallet'
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=0),
                name='portal_wallet_balance_non_negative',
            ),
        ]

    def __str__(self):
        return f"Wallet for {self.user.username} - {self.balance} {self.currency}"
    
    def get_decrypted_seed_phrase(self) -> str:
        """Get decrypted seed phrase"""
        if self.encrypted_seed_phrase:
            try:
                return decrypt_data(self.encrypted_seed_phrase)
            except (ValueError, TypeError) as e:
                logger.warning(
                    'Failed to decrypt seed phrase for wallet pk=%s: %s',
                    self.pk,
                    e,
                    exc_info=True
                )
                return ""
        return ""
    
    def set_encrypted_seed_phrase(self, seed_phrase: str) -> None:
        """Set encrypted seed phrase"""
        if seed_phrase:
            self.encrypted_seed_phrase = encrypt_data(seed_phrase)
        else:
            self.encrypted_seed_phrase = None

    history = HistoricalRecords(
        inherit=False,
        excluded_fields=['created_at', 'updated_at', 'encrypted_seed_phrase'],
        user_model=settings.AUTH_USER_MODEL,
    )


class WalletTransaction(models.Model):
    """Wallet transaction model"""
    
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    
    balance_before = models.DecimalField(max_digits=20, decimal_places=2)
    balance_after = models.DecimalField(max_digits=20, decimal_places=2)
    
    reference = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Audit and idempotency (used by WalletService and partner accounting)
    description = models.TextField(blank=True, null=True, help_text="Transaction description")
    reference_id = models.CharField(
        max_length=255, blank=True, null=True, db_index=True,
        help_text="External reference ID for idempotency/audit"
    )
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional transaction metadata")
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_wallet_transactions",
        help_text="User who performed the transaction",
    )
    
    # Encrypted transaction details
    encrypted_details = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'portal_wallet_transaction'
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type} {self.amount} - {self.wallet.user.username}"

    history = HistoricalRecords(
        inherit=False,
        excluded_fields=['created_at', 'encrypted_details'],
        user_model=settings.AUTH_USER_MODEL,
    )


# =============================================================================
# PARKPE VOUCHER (no wallet in ParkPe – customer pays via PG or voucher balance)
# =============================================================================

class ParkPeVoucherBalance(models.Model):
    """
    ParkPe user's voucher balance. One row per user.
    Credits when user buys voucher via PG; debits when user pays with voucher (e.g. BBPS).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='parkpe_voucher_balance',
    )
    balance = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text='Available voucher balance in INR',
    )
    currency = models.CharField(max_length=3, default='INR')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_parkpe_voucher_balance'
        verbose_name = 'ParkPe Voucher Balance'
        verbose_name_plural = 'ParkPe Voucher Balances'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=0),
                name='parkpe_voucher_balance_non_negative',
            ),
        ]

    def __str__(self):
        return f"ParkPe voucher {self.user.username}: {self.balance} {self.currency}"


class ParkPeVoucherTransaction(models.Model):
    """Audit trail for ParkPe voucher credit/debit."""
    CREDIT = 'credit'
    DEBIT = 'debit'
    TYPE_CHOICES = [(CREDIT, 'Credit'), (DEBIT, 'Debit')]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='parkpe_voucher_transactions',
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES, db_index=True)
    balance_after = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    reference_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    service_code = models.CharField(max_length=50, blank=True, null=True, help_text='e.g. BBPS, voucher_purchase')
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'portal_parkpe_voucher_transaction'
        verbose_name = 'ParkPe Voucher Transaction'
        verbose_name_plural = 'ParkPe Voucher Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.transaction_type} {self.amount} – user {self.user_id}"


class ServiceVoucherRefundCase(models.Model):
    """
    When a voucher debit succeeded but the downstream service did not complete (e.g. RC API error),
    queue a case for admin review. Refund credits the same GiftVoucher balance and records:
    - ParkPeVoucherTransaction CREDIT with reference_id = original debit reference (reconciliation).
    - GiftVoucherTransaction with a new unique transaction_ref (DB constraint) and metadata linking
      to the original debit ref (voucher ledger cannot reuse the same transaction_ref row).
    """

    STATUS_OPEN = "open"
    STATUS_REFUNDED = "refunded"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_REFUNDED, "Refunded"),
        (STATUS_DISMISSED, "Dismissed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="service_voucher_refund_cases",
    )
    vehicle = models.ForeignKey(
        "Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_voucher_refund_cases",
    )
    debit_reference_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Original transaction ref used for voucher redemption and ParkPe DEBIT row",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    service_code = models.CharField(max_length=50, default="RC_VIEW", db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    rc_reason_code = models.CharField(max_length=64, blank=True, default="")
    failure_detail = models.TextField(blank=True, default="")
    source = models.CharField(
        max_length=32,
        default="auto_fetch_failed",
        help_text="auto_fetch_failed | manual (future)",
    )
    admin_narration = models.TextField(blank=True, default="")
    credit_transaction_ref = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="GiftVoucherTransaction.transaction_ref for the refund credit line (unique)",
    )
    refunded_at = models.DateTimeField(null=True, blank=True)
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_voucher_refunds_processed",
    )
    dismissed_at = models.DateTimeField(null=True, blank=True)
    dismissed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_voucher_refund_cases_dismissed",
    )
    dismiss_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_service_voucher_refund_case"
        verbose_name = "Service voucher refund case"
        verbose_name_plural = "Service voucher refund cases"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["service_code", "status"]),
        ]

    def __str__(self):
        return f"{self.service_code} {self.debit_reference_id} ({self.status})"


class TaxServiceProfile(models.Model):
    """
    GST/TDS configuration per service_code and document subtype (B2C receipt vs B2B commission).
    Amounts on BillingDocument are snapshotted; changing this row does not alter past documents.
    """

    DOC_B2C = "b2c_receipt"
    DOC_B2B = "b2b_commission"
    DOCUMENT_SUBTYPE_CHOICES = [
        (DOC_B2C, "B2C receipt"),
        (DOC_B2B, "B2B commission"),
    ]

    service_code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Lowercase logical code e.g. bbps, rc_view, voucher_purchase, partner_commission",
    )
    document_subtype = models.CharField(
        max_length=32,
        choices=DOCUMENT_SUBTYPE_CHOICES,
        default=DOC_B2C,
        db_index=True,
    )
    sac_or_hsn = models.CharField(max_length=32, blank=True, default="", help_text="SAC or HSN label for receipts")
    gst_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
        help_text="Combined GST % (intra-state CGST+SGST derived as half each)",
    )
    gst_inclusive = models.BooleanField(
        default=True,
        help_text="If true, input amount is tax-inclusive (typical B2C)",
    )
    is_gst_exempt = models.BooleanField(default=True)
    is_pass_through = models.BooleanField(
        default=False,
        help_text="If true: no GST on Payswap share; receipt still shows customer amount",
    )
    tds_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="TDS % on taxable base (mainly B2B commission)",
    )
    effective_from = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_tax_service_profile"
        verbose_name = "Tax service profile"
        verbose_name_plural = "Tax service profiles"
        constraints = [
            models.UniqueConstraint(
                fields=["service_code", "document_subtype"],
                name="portal_tax_profile_service_subtype_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.service_code}/{self.document_subtype} GST={self.gst_rate}%"


class BillingDocument(models.Model):
    """
    Immutable tax/receipt document for a commercial event (B2C, credit note, or B2B commission stub).
    """

    DOC_B2C_RECEIPT = "b2c_receipt"
    DOC_CREDIT_NOTE = "credit_note"
    DOC_B2B_COMMISSION = "b2b_commission_invoice"
    DOCUMENT_TYPE_CHOICES = [
        (DOC_B2C_RECEIPT, "B2C receipt"),
        (DOC_CREDIT_NOTE, "Credit note"),
        (DOC_B2B_COMMISSION, "B2B commission invoice"),
    ]

    document_type = models.CharField(max_length=40, choices=DOCUMENT_TYPE_CHOICES, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="billing_documents",
    )
    partner = models.ForeignKey(
        "ResellerPartner",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="billing_documents",
    )
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)
    reference_id = models.CharField(max_length=255, db_index=True)
    service_code = models.CharField(max_length=50, db_index=True)
    transaction_direction = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="credit or debit when tied to ParkPe voucher ledger",
    )
    taxable_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gst_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tds_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    snapshot = models.JSONField(default=dict, blank=True)
    currency = models.CharField(max_length=3, default="INR")
    parkpe_voucher_transaction = models.ForeignKey(
        "ParkPeVoucherTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_documents",
    )
    issued_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_billing_document"
        verbose_name = "Billing document"
        verbose_name_plural = "Billing documents"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["user", "-issued_at"]),
            models.Index(fields=["partner", "-issued_at"]),
            models.Index(fields=["service_code", "-issued_at"]),
        ]

    def __str__(self):
        return f"{self.document_type} {self.reference_id} ₹{self.grand_total}"


class ParkPeServiceConfig(models.Model):
    """
    Per-service config for ParkPe: which services allow voucher and/or PG.
    service_code e.g. 'BBPS', 'voucher_purchase' (purchase flow is not a biller service).
    """
    service_code = models.CharField(max_length=50, unique=True, db_index=True)
    voucher_allowed = models.BooleanField(default=True, help_text='User can pay with voucher balance')
    pg_allowed = models.BooleanField(default=True, help_text='User can pay with PG (Razorpay/Cashfree)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_parkpe_service_config'
        verbose_name = 'ParkPe Service Config'
        verbose_name_plural = 'ParkPe Service Configs'

    def __str__(self):
        return f"{self.service_code} (voucher={self.voucher_allowed}, pg={self.pg_allowed})"


class ParkPePaymentGatewayConfig(models.Model):
    """
    Which PG is enabled for ParkPe and for which use (voucher purchase vs specific service).
    service_code null = used for voucher purchase (create-order). Non-null = for that service's PG pay.
    """
    RAZORPAY = 'razorpay'
    CASHFREE = 'cashfree'
    GATEWAY_CHOICES = [(RAZORPAY, 'Razorpay'), (CASHFREE, 'Cashfree')]

    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, db_index=True)
    enabled = models.BooleanField(default=True)
    service_code = models.CharField(
        max_length=50,
        default='',
        blank=True,
        db_index=True,
        help_text='Empty = voucher purchase; e.g. BBPS = PG for BBPS pay',
    )
    merchant_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='Merchant identifier (e.g. MCH_001). Isse pata chalega ki is gateway+service ke liye kaun sa merchant account use ho raha hai.',
    )
    credential_key = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Razorpay: Key ID. Cashfree: App ID (x-client-id). Optional if using single merchant from .env (RAZORPAY_KEY_ID / CASHFREE_PG_CLIENT_ID).',
    )
    is_default_for_voucher_purchase = models.BooleanField(
        default=False,
        help_text='Use this config when creating voucher purchase orders (service_code empty)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_parkpe_payment_gateway_config'
        verbose_name = 'ParkPe Payment Gateway Config'
        verbose_name_plural = 'ParkPe Payment Gateway Configs'
        constraints = [
            models.UniqueConstraint(
                fields=['gateway', 'service_code'],
                name='parkpe_pg_config_gateway_service_unique',
            ),
        ]

    def __str__(self):
        return f"{self.gateway} service={self.service_code or 'voucher_purchase'}"


class ParkPePaymentOrder(models.Model):
    """Pending PG order for ParkPe (e.g. voucher purchase). Verified orders get voucher credit."""
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    STATUS_CHOICES = [(PENDING, 'Pending'), (COMPLETED, 'Completed'), (FAILED, 'Failed')]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='parkpe_payment_orders',
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    gateway = models.CharField(max_length=20, db_index=True)
    order_id = models.CharField(max_length=255, db_index=True, help_text='PG order id (e.g. Razorpay order_id)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    reference_id = models.CharField(max_length=255, blank=True, null=True, help_text='PG payment_id after verify')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_parkpe_payment_order'
        verbose_name = 'ParkPe Payment Order'
        verbose_name_plural = 'ParkPe Payment Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"ParkPe order {self.order_id} {self.status}"


class ParkPeBBPSFavoriteBiller(models.Model):
    """ParkPe BBPS favorite biller – stored in DB so it syncs across devices."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='parkpe_bbps_favorites',
    )
    operator_id = models.CharField(max_length=128, db_index=True)
    operator_name = models.CharField(max_length=255, default='')
    category = models.CharField(max_length=64, default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'portal_parkpe_bbps_favorite_biller'
        verbose_name = 'ParkPe BBPS Favorite Biller'
        verbose_name_plural = 'ParkPe BBPS Favorite Billers'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'operator_id'],
                name='parkpe_bbps_fav_user_operator_unique',
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_id} favorite {self.operator_id}"


class ParkPeBBPSSavedBill(models.Model):
    """ParkPe BBPS saved bill – stored in DB so it syncs across devices."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='parkpe_bbps_saved_bills',
    )
    nickname = models.CharField(max_length=128, blank=True, default='')
    operator_id = models.CharField(max_length=128, db_index=True)
    operator_name = models.CharField(max_length=255, default='')
    category = models.CharField(max_length=64, default='', blank=True)
    consumer_id = models.CharField(max_length=255)
    last_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Last known bill amount',
    )
    bill_id = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'portal_parkpe_bbps_saved_bill'
        verbose_name = 'ParkPe BBPS Saved Bill'
        verbose_name_plural = 'ParkPe BBPS Saved Bills'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_id} saved {self.operator_name} {self.consumer_id}"


class ParkPeBBPSBillPaymentRecord(models.Model):
    """
    One row per Mobikwik BBPS reference_id (T… bill pay ref).
    Updated on pay response and on each pay-status poll — used when vendor API is unavailable.
    """
    PHASE_PENDING = "pending"
    PHASE_SUCCESS = "success"
    PHASE_FAILED = "failed"
    PHASE_CHOICES = [
        (PHASE_PENDING, "Pending"),
        (PHASE_SUCCESS, "Success"),
        (PHASE_FAILED, "Failed"),
    ]

    reference_id = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parkpe_bbps_bill_payments",
    )
    operator_id = models.CharField(max_length=128, blank=True, default="")
    bill_id = models.CharField(max_length=128, blank=True, default="")
    consumer_id = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    payment_method = models.CharField(max_length=32, blank=True, default="")
    vendor = models.CharField(max_length=32, default="mobikwik")
    last_vendor_status = models.CharField(max_length=255, blank=True, default="")
    resolved_phase = models.CharField(
        max_length=16, choices=PHASE_CHOICES, default=PHASE_PENDING, db_index=True
    )
    pay_response_json = models.JSONField(null=True, blank=True)
    last_poll_json = models.JSONField(null=True, blank=True)
    last_error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_status_check_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "portal_parkpe_bbps_bill_payment_record"
        verbose_name = "ParkPe BBPS bill payment record"
        verbose_name_plural = "ParkPe BBPS bill payment records"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.reference_id} ({self.resolved_phase})"


class ParkPeChallanRecord(models.Model):
    """
    Cached challan records per user+vehicle to avoid repeat vendor calls.
    Refreshed on explicit user refresh and on pending-detail rechecks.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parkpe_challans",
    )
    vehicle_number = models.CharField(max_length=32, db_index=True)
    challan_number = models.CharField(max_length=128, db_index=True)
    challan_id = models.CharField(max_length=255, db_index=True, blank=True, default="")
    status = models.CharField(max_length=32, blank=True, default="pending", db_index=True)
    state = models.CharField(max_length=16, blank=True, default="")
    offence = models.TextField(blank=True, default="")
    offence_date = models.CharField(max_length=64, blank=True, default="")
    location = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    penalty_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, blank=True, default="INR")
    vehicle_owner_name = models.CharField(max_length=255, blank=True, default="")
    issuing_authority = models.CharField(max_length=255, blank=True, default="")
    officer_name = models.CharField(max_length=255, blank=True, default="")
    due_date = models.CharField(max_length=64, blank=True, default="")
    payment_deadline = models.CharField(max_length=64, blank=True, default="")
    payload_json = models.JSONField(null=True, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_parkpe_challan_record"
        verbose_name = "ParkPe Challan Record"
        verbose_name_plural = "ParkPe Challan Records"
        ordering = ["-last_seen_at", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "vehicle_number", "challan_number"],
                name="uniq_parkpe_challan_user_vehicle_number",
            )
        ]
        indexes = [
            models.Index(fields=["user", "vehicle_number", "-last_seen_at"]),
            models.Index(fields=["user", "status", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.vehicle_number} · {self.challan_number} ({self.status})"


class UserPermission(models.Model):
    """Custom user permission assignments"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='custom_permissions'
    )
    
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='user_assignments'
    )
    
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_permissions'
    )
    
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_user_permissions'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'portal_user_permission'
        verbose_name = 'User Permission'
        verbose_name_plural = 'User Permissions'
        unique_together = ['user', 'permission']
        ordering = ['-granted_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.permission}"
    
    def revoke(self, revoked_by: User = None) -> None:
        """Revoke permission and record who revoked it for auditability."""
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoked_by = revoked_by
        self.save()


class LogEntry(models.Model):
    """
    Internal log management system - stores all application logs in database
    for querying, analysis, and issue tracking
    """
    
    LOG_LEVEL_CHOICES = [
        ('DEBUG', 'DEBUG'),
        ('INFO', 'INFO'),
        ('WARNING', 'WARNING'),
        ('ERROR', 'ERROR'),
        ('CRITICAL', 'CRITICAL'),
    ]
    
    CATEGORY_CHOICES = [
        ('api', 'API'),
        ('api_explorer', 'API Explorer Tests'),
        ('auth', 'Authentication'),
        ('payment', 'Payment'),
        ('notification', 'Notification'),
        ('security', 'Security'),
        ('cashfree', 'Cashfree API'),
        ('cashfree_pg', 'Cashfree PG API'),
        ('kaleyra', 'Kaleyra API'),
        ('leegality', 'Leegality API'),
        ('mobikwik_bbps', 'Mobikwik BBPS API'),
        ('gift_voucher', 'Gift Voucher'),
        ('connect_vehicle', 'Connect Vehicle'),
        ('parkpe_auth', 'ParkPe Auth'),
        ('parkpe_bbps', 'ParkPe BBPS'),
        ('parkpe_voucher', 'ParkPe Voucher'),
        ('parkpe_payment', 'ParkPe Payment'),
        ('parkpe_connect', 'ParkPe Connect'),
        ('parkpe_dashboard', 'ParkPe Dashboard'),
        ('parkpe_fastag', 'ParkPe FASTag'),
        ('parkpe_challan', 'ParkPe Challan'),
        ('parkpe_general', 'ParkPe General'),
        ('instantpay', 'Instantpay API'),
        ('general', 'General'),
    ]

    LOG_ROLE_CHOICES = [
        ('client', 'Client / app request'),
        ('vendor', 'Vendor API'),
        ('system', 'System / downstream'),
    ]
    
    # ============================================================================
    # BASIC INFORMATION
    # ============================================================================
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, help_text="When the log entry was created")
    log_level = models.CharField(max_length=10, choices=LOG_LEVEL_CHOICES, db_index=True, help_text="Log severity level")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general', db_index=True, help_text="Log category")
    message = models.TextField(help_text="Log message")
    
    # ============================================================================
    # CONTEXT INFORMATION
    # ============================================================================
    module_name = models.CharField(max_length=200, blank=True, null=True, db_index=True, help_text="Module where event occurred")
    url = models.CharField(max_length=500, blank=True, null=True, db_index=True, help_text="URL path for the request")
    request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, help_text="Request ID for tracing")
    response_id = models.CharField(max_length=100, blank=True, null=True, help_text="Response ID")
    correlation_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Ties client + vendor rows in one flow (often same as X-Request-ID)",
    )
    chain_step = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        db_index=True,
        help_text="1=app/client, 2=first vendor, higher=downstream",
    )
    log_role = models.CharField(
        max_length=16,
        choices=LOG_ROLE_CHOICES,
        blank=True,
        null=True,
        help_text="Position in request chain",
    )
    
    # ============================================================================
    # USER INFORMATION
    # ============================================================================
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='log_entries',
        db_index=True,
        help_text="User who triggered the action (if applicable)"
    )
    
    # ============================================================================
    # REQUEST INFORMATION
    # ============================================================================
    client_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True, help_text="Client IP address")
    user_agent = models.TextField(blank=True, null=True, help_text="User agent string")
    session_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, help_text="Session ID")
    
    # ============================================================================
    # ADDITIONAL DATA
    # ============================================================================
    extra_data = models.JSONField(default=dict, blank=True, null=True, help_text="Additional structured data (sanitized)")
    
    # ============================================================================
    # ERROR INFORMATION
    # ============================================================================
    traceback = models.TextField(blank=True, null=True, help_text="Error traceback (for errors only)")
    exception_type = models.CharField(max_length=200, blank=True, null=True, help_text="Exception type if error occurred")
    
    # ============================================================================
    # METADATA
    # ============================================================================
    resolved = models.BooleanField(default=False, db_index=True, help_text="Whether this log entry has been resolved/reviewed")
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="When this log was resolved")
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_logs',
        help_text="User who resolved this log entry"
    )
    notes = models.TextField(blank=True, null=True, help_text="Admin notes about this log entry")
    
    class Meta:
        db_table = 'portal_log_entry'
        verbose_name = 'Log Entry'
        verbose_name_plural = 'Log Entries'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'log_level']),
            models.Index(fields=['category', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['request_id']),
            models.Index(fields=['correlation_id', 'chain_step', 'timestamp']),
            models.Index(fields=['resolved', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.log_level} - {self.message[:50]} - {self.timestamp}"
    
    def mark_resolved(self, resolved_by: User = None, notes: str = None):
        """Mark this log entry as resolved"""
        self.resolved = True
        self.resolved_at = timezone.now()
        if resolved_by:
            self.resolved_by = resolved_by
        if notes:
            self.notes = notes
        self.save(update_fields=['resolved', 'resolved_at', 'resolved_by', 'notes'])
    
    def mark_unresolved(self):
        """Mark this log entry as unresolved"""
        self.resolved = False
        self.resolved_at = None
        self.resolved_by = None
        self.save(update_fields=['resolved', 'resolved_at', 'resolved_by'])

    @property
    def hub_category_label(self) -> str:
        """Category + vendor name for Hub /logs list (avoids cluttering CATEGORY_CHOICES)."""
        base = self.get_category_display() if self.category else "—"
        ex = self.extra_data or {}
        v = ex.get("vendor") or ex.get("vendor_name")
        if v and str(v) not in base:
            return f"{base} · {v}"
        return base


class EmailQueue(models.Model):
    """
    Durable email queue: source of truth for outbound emails.
    Never send email directly from request/transaction; always enqueue here.
    Survives Celery crashes; resend_pending_emails recovers without Celery.
    """
    STATUS_PENDING = 'PENDING'
    STATUS_SENT = 'SENT'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    to_email = models.EmailField()
    subject = models.CharField(max_length=512)
    body_html = models.TextField(blank=True, null=True)
    body_text = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    retry_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, null=True)
    # Related entity: voucher_id, order_id, etc. (JSON: {"type": "voucher", "voucher_id": 123})
    related_entity = models.JSONField(blank=True, null=True)
    use_parkpe_smtp = models.BooleanField(default=False, help_text='Use Parkpe SMTP (voucher emails)')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'portal_email_queue'
        verbose_name = 'Email Queue'
        verbose_name_plural = 'Email Queue'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'EmailQueue(id={self.id}, to={self.to_email[:8]}..., status={self.status})'


class CashfreeAPILog(models.Model):
    """
    Detailed logging for Cashfree API calls
    Stores request/response data, timing, errors, etc.
    """
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
        ('failed', 'Failed'),
    ]
    
    API_TYPE_CHOICES = [
        ('pan', 'PAN Verification'),
        ('aadhaar', 'Aadhaar Verification'),
        ('bank', 'Bank Account Verification'),
        ('driving_license', 'Driving License Verification'),
        ('voter_id', 'Voter ID Verification'),
        ('passport', 'Passport Verification'),
        ('gst', 'GST Verification'),
        ('cin', 'CIN Verification'),
        ('ifsc', 'IFSC Verification'),
        ('vehicle_rc', 'Vehicle RC Verification'),
        ('face_liveness', 'Face Liveness'),
        ('face_match', 'Face Match'),
        ('name_match', 'Name Match'),
        ('smart_ocr', 'Smart OCR'),
        ('phone', 'Phone Verification'),
        ('email', 'Email Verification'),
        ('test_connection', 'Test Connection'),
    ]
    
    # ============================================================================
    # BASIC INFORMATION
    # ============================================================================
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, help_text="When the API call was made")
    api_type = models.CharField(max_length=50, choices=API_TYPE_CHOICES, db_index=True, help_text="Type of API call")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True, help_text="API call status")
    
    # ============================================================================
    # REQUEST INFORMATION
    # ============================================================================
    endpoint = models.CharField(max_length=200, help_text="API endpoint called")
    method = models.CharField(max_length=10, default='POST', help_text="HTTP method")
    request_payload = models.JSONField(null=True, blank=True, help_text="Request payload (sanitized)")
    verification_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, help_text="Cashfree verification ID")
    
    # ============================================================================
    # RESPONSE INFORMATION
    # ============================================================================
    response_data = models.JSONField(null=True, blank=True, help_text="Response data from API")
    status_code = models.IntegerField(null=True, blank=True, help_text="HTTP status code")
    response_time = models.FloatField(null=True, blank=True, help_text="Response time in seconds")
    
    # ============================================================================
    # ERROR INFORMATION
    # ============================================================================
    error_message = models.TextField(blank=True, null=True, help_text="Error message if call failed")
    error_code = models.CharField(max_length=100, blank=True, null=True, help_text="Error code from API")
    error_type = models.CharField(max_length=200, blank=True, null=True, help_text="Error type")
    traceback = models.TextField(blank=True, null=True, help_text="Error traceback")
    
    # ============================================================================
    # USER INFORMATION
    # ============================================================================
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cashfree_api_logs',
        db_index=True,
        help_text="User who made the API call"
    )
    
    # ============================================================================
    # METADATA
    # ============================================================================
    request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, help_text="Request ID for tracing")
    client_ip = models.GenericIPAddressField(null=True, blank=True, help_text="Client IP address")
    user_agent = models.TextField(blank=True, null=True, help_text="User agent string")
    
    # Link to main log entry
    log_entry = models.ForeignKey(
        LogEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cashfree_api_logs',
        help_text="Related LogEntry for unified logging"
    )
    
    class Meta:
        db_table = 'portal_cashfree_api_log'
        verbose_name = 'Cashfree API Log'
        verbose_name_plural = 'Cashfree API Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'status']),
            models.Index(fields=['api_type', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['verification_id']),
            models.Index(fields=['status', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.api_type} - {self.status} - {self.timestamp}"


# ============================================================================
# SERVICES MANAGEMENT MODELS
# ============================================================================

class Service(models.Model):
    """
    Service model for API integrations
    Stores services that will be integrated via API
    """
    SERVICE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
    ]
    
    name = models.CharField(max_length=100, unique=True, help_text="Service name (e.g., BBPS, AEPS)")
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="Service code (e.g., BBPS, AEPS)")
    description = models.TextField(blank=True, null=True, help_text="Service description")
    status = models.CharField(max_length=20, choices=SERVICE_STATUS_CHOICES, default='pending', db_index=True, help_text="Service status")
    
    # API Integration fields
    api_provider = models.CharField(max_length=100, blank=True, null=True, help_text="API provider name")
    api_endpoint = models.URLField(blank=True, null=True, help_text="API endpoint URL")
    api_key = models.CharField(max_length=255, blank=True, null=True, help_text="API key (encrypted)")
    api_secret = models.CharField(max_length=255, blank=True, null=True, help_text="API secret (encrypted)")
    
    # Configuration
    is_enabled = models.BooleanField(default=False, help_text="Whether service is enabled")
    requires_kyc = models.BooleanField(default=True, help_text="Whether service requires KYC verification")
    min_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Minimum balance required")
    
    # Vendor service configurations (JSON field to store vendor-wise service enable/disable status)
    vendor_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Vendor service configurations - stores which services are enabled/disabled per vendor"
    )
    
    # Category for flow-based orchestration (AEPS, DMT, BBPS, FASTAG, etc.)
    category = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text="Service category for orchestration (AEPS, DMT, BBPS, etc.)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_services',
        help_text="User who created this service"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_services',
        help_text="User who last updated this service"
    )
    
    history = HistoricalRecords(
        inherit=False,
        excluded_fields=['created_at', 'updated_at', 'api_key', 'api_secret'],
        user_model=settings.AUTH_USER_MODEL,
    )

    class Meta:
        db_table = 'portal_service'
        verbose_name = 'Service'
        verbose_name_plural = 'Services'
        ordering = ['name']
        indexes = [
            models.Index(fields=['code', 'status']),
            models.Index(fields=['is_enabled', 'status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def save(self, *args, **kwargs):
        # Auto-generate code from name if not provided
        if not self.code and self.name:
            self.code = self.name.upper().replace(' ', '_')
        super().save(*args, **kwargs)


# ============================================================================
# VENDOR-ORCHESTRATED SERVICE FLOW (First-class vendors, APIs, ordered steps)
# ============================================================================

class ApiVendor(models.Model):
    """
    API Vendor - first-class entity (PayPoint, Euronet, M2P, etc.).
    Vendors provide APIs; services are orchestrated flows over vendor APIs.
    """
    name = models.CharField(max_length=100, help_text="Vendor name (e.g. PayPoint, Euronet)")
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique slug (e.g. paypoint, euronet)")
    is_active = models.BooleanField(default=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_apivendor'
        verbose_name = 'API Vendor'
        verbose_name_plural = 'API Vendors'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class VendorApi(models.Model):
    """
    One callable API capability provided by a vendor.
    No business flow logic here; flow is defined by ServiceFlowStep.
    """
    API_TYPE_CHOICES = [
        ('SETUP', 'Setup'),
        ('VALIDATION', 'Validation'),
        ('AUTH', 'Authentication'),
        ('TRANSACTION', 'Transaction'),
        ('2FA', 'Two Factor Auth'),
        ('QUERY', 'Query'),
    ]
    vendor = models.ForeignKey(ApiVendor, on_delete=models.CASCADE, related_name='apis')
    name = models.CharField(max_length=150, help_text="e.g. Add Agent, AEPS Balance Enquiry")
    api_code = models.CharField(max_length=80, help_text="Unique per vendor (e.g. add_agent, balance_enquiry)")
    api_type = models.CharField(max_length=20, choices=API_TYPE_CHOICES, default='TRANSACTION', db_index=True)
    purpose = models.CharField(max_length=255, blank=True, null=True, help_text="API purpose / one-line description for orchestration")
    endpoint_url = models.URLField(blank=True, null=True, help_text="Optional; actual call may be via registered handler")
    http_method = models.CharField(max_length=10, default='POST', blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    timeout_seconds = models.PositiveIntegerField(default=30, blank=True)
    retry_allowed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_vendorapi'
        verbose_name = 'Vendor API'
        verbose_name_plural = 'Vendor APIs'
        unique_together = [['vendor', 'api_code']]
        ordering = ['vendor', 'api_code']

    def __str__(self):
        return f"{self.vendor.code}:{self.api_code}"


class ServiceFlowStep(models.Model):
    """
    One step in a service's execution flow. Order is defined by step_order.
    Same VendorApi can appear in multiple services. Execution is data-driven.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='flow_steps')
    vendor = models.ForeignKey(ApiVendor, on_delete=models.PROTECT, related_name='flow_steps')
    vendor_api = models.ForeignKey(VendorApi, on_delete=models.PROTECT, related_name='flow_steps')
    step_order = models.PositiveIntegerField(help_text="Execution order; unique per service")
    step_name = models.CharField(max_length=150, help_text="Display name (e.g. Add Agent, Check Authentication)")
    is_mandatory = models.BooleanField(default=True)
    halt_on_failure = models.BooleanField(default=True, help_text="Stop flow if this step fails")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_serviceflowstep'
        verbose_name = 'Service Flow Step'
        verbose_name_plural = 'Service Flow Steps'
        unique_together = [['service', 'step_order']]
        ordering = ['service', 'step_order']

    def __str__(self):
        return f"{self.service.code} #{self.step_order}: {self.step_name}"

    def clean(self):
        if self.vendor_id and self.vendor_api_id and self.vendor_api.vendor_id != self.vendor_id:
            raise ValidationError("vendor_api must belong to the selected vendor.")


class ServiceCost(models.Model):
    """
    Service Cost model to track our cost per service/product
    This is the cost we pay to vendors for using their APIs
    Used to calculate partner pricing and margins
    """
    
    COST_TYPE_CHOICES = [
        ('FIXED', 'Fixed Amount'),
        ('PERCENTAGE', 'Percentage'),
        ('PER_TRANSACTION', 'Per Transaction'),
        ('TIERED', 'Tiered Pricing'),
    ]
    
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='costs',
        help_text="Service this cost applies to"
    )
    
    # Cost Configuration
    cost_type = models.CharField(
        max_length=20,
        choices=COST_TYPE_CHOICES,
        default='FIXED',
        help_text="Type of cost model"
    )
    base_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Base cost for the service (what we pay vendor)"
    )
    cost_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Cost percentage (if cost_type is PERCENTAGE)"
    )
    cost_per_transaction = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Cost per transaction (if cost_type is PER_TRANSACTION)"
    )
    
    # Tiered Cost (stored as JSON)
    tiered_cost = models.JSONField(
        default=list,
        blank=True,
        help_text="Tiered cost structure: [{'min': 0, 'max': 1000, 'cost': 2.5}, ...]"
    )
    
    # Service-specific fields
    provides_commission = models.BooleanField(
        default=False,
        help_text="Whether this service provides commission (e.g., AEPS, DMT, BBPS)"
    )
    commission_on = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Who gets commission (e.g., 'sender', 'receiver', 'partner')"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this cost configuration is active"
    )
    effective_from = models.DateTimeField(
        default=timezone.now,
        help_text="When this cost becomes effective"
    )
    effective_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this cost expires (null = never expires)"
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes about this cost configuration"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_service_costs',
        help_text="User who created this cost"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portal_service_cost'
        verbose_name = 'Service Cost'
        verbose_name_plural = 'Service Costs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service', 'is_active']),
            models.Index(fields=['is_active', 'effective_from']),
        ]
    
    def __str__(self):
        return f"{self.service.name} Cost - {self.cost_type}"
    
    def calculate_cost(self, amount=None, transaction_count=1):
        """
        Calculate cost based on cost type
        
        Args:
            amount: Transaction amount (for percentage-based costs)
            transaction_count: Number of transactions (for per-transaction costs)
        
        Returns:
            Calculated cost
        """
        from decimal import Decimal
        
        if self.cost_type == 'FIXED':
            return self.base_cost
        elif self.cost_type == 'PERCENTAGE':
            if amount:
                return amount * self.cost_percentage / 100
            return Decimal('0.00')
        elif self.cost_type == 'PER_TRANSACTION':
            return self.cost_per_transaction * transaction_count
        elif self.cost_type == 'TIERED':
            if amount:
                for tier in self.tiered_cost:
                    if tier.get('min', 0) <= amount <= tier.get('max', float('inf')):
                        return Decimal(str(tier.get('cost', 0)))
            return Decimal('0.00')
        return Decimal('0.00')


class BBPSBillerCategory(models.Model):
    """
    BBPS Biller Category model for biller-specific commission setup
    Each biller category can have different commission rates
    """
    
    CATEGORY_CHOICES = [
        ('ELECTRICITY', 'Electricity'),
        ('WATER', 'Water'),
        ('GAS', 'Gas'),
        ('MOBILE_PREPAID', 'Mobile Prepaid'),
        ('MOBILE_POSTPAID', 'Mobile Postpaid'),
        ('LANDLINE', 'Landline'),
        ('BROADBAND', 'Broadband'),
        ('DTH', 'DTH'),
        ('INSURANCE', 'Insurance'),
        ('LOAN', 'Loan'),
        ('CREDIT_CARD', 'Credit Card'),
        ('FASTAG', 'Fastag'),
        ('MUNICIPAL', 'Municipal'),
        ('EDUCATION', 'Education'),
        ('HEALTHCARE', 'Healthcare'),
        ('OTHER', 'Other'),
    ]
    
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='biller_categories',
        limit_choices_to={'code': 'BBPS'},
        help_text="BBPS service"
    )
    
    category_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Biller category code (e.g., ELECTRICITY, WATER)"
    )
    category_name = models.CharField(
        max_length=100,
        help_text="Biller category name"
    )
    category_type = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        help_text="Type of biller category"
    )
    
    # Commission Configuration
    COMMISSION_TYPE_CHOICES = [
        ('REVENUE_SHARE', 'Revenue Share'),
        ('MARKUP', 'Markup'),
        ('FIXED_COMMISSION', 'Fixed Commission'),
    ]
    
    commission_type = models.CharField(
        max_length=20,
        choices=COMMISSION_TYPE_CHOICES,
        default='REVENUE_SHARE',
        help_text="Type of commission model"
    )
    default_commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Default commission percentage for this category"
    )
    default_fixed_commission = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Default fixed commission for this category"
    )
    
    # Cost Configuration
    base_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Base cost for this biller category"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this biller category is active"
    )
    
    # Metadata
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description of this biller category"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portal_bbps_biller_category'
        verbose_name = 'BBPS Biller Category'
        verbose_name_plural = 'BBPS Biller Categories'
        ordering = ['category_name']
        indexes = [
            models.Index(fields=['service', 'is_active']),
            models.Index(fields=['category_code', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.category_name} ({self.category_code})"


class HubVendorCostRecord(models.Model):
    """
    Hub cost: SMS, IVR, Cashfree API usage (what we pay vendors).
    One row per usage event or aggregated per period.
    """
    SERVICE_CODE_CHOICES = [
        ('sms', 'SMS'),
        ('ivr', 'IVR / Click-to-Call'),
        ('cashfree_pg', 'Cashfree PG'),
        ('cashfree_rc', 'Cashfree RC'),
        ('cashfree_kyc', 'Cashfree KYC'),
    ]
    service_code = models.CharField(max_length=30, choices=SERVICE_CODE_CHOICES, db_index=True)
    vendor_code = models.CharField(max_length=50, db_index=True, help_text='e.g. kaleyra, cashfree')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Cost in INR')
    unit_count = models.PositiveIntegerField(default=1, help_text='e.g. 1 SMS, 1 call')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    period_date = models.DateField(null=True, blank=True, db_index=True)
    reference_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    partner = models.ForeignKey(
        'portal.ResellerPartner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hub_cost_records',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'portal_hub_vendor_cost_record'
        verbose_name = 'Hub Vendor Cost Record'
        verbose_name_plural = 'Hub Vendor Cost Records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service_code', 'period_date']),
            models.Index(fields=['vendor_code', 'created_at']),
        ]

    def __str__(self):
        return f"{self.service_code} {self.vendor_code} {self.amount} @ {self.created_at}"


class HubCostRateConfig(models.Model):
    """Admin-configurable unit cost for Hub vendor usage (SMS, IVR, Cashfree)."""
    service_code = models.CharField(max_length=30, db_index=True)  # sms, ivr, cashfree_pg, etc.
    vendor_code = models.CharField(max_length=50, db_index=True, default='')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_hub_cost_rate_config'
        verbose_name = 'Hub Cost Rate Config'
        unique_together = [['service_code', 'vendor_code']]

    def __str__(self):
        return f"{self.service_code}/{self.vendor_code} = {self.unit_cost}"


class HubIncomeRecord(models.Model):
    """
    Hub income: BBPS commission, Voucher margin (what we earn).
    One row per successful income event.
    """
    SERVICE_CODE_CHOICES = [
        ('bbps', 'BBPS'),
        ('voucher', 'Voucher'),
    ]
    service_code = models.CharField(max_length=30, choices=SERVICE_CODE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Income in INR')
    transaction_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text='Original txn amount if applicable')
    vendor_code = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    reference_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    partner = models.ForeignKey(
        'portal.ResellerPartner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hub_income_records',
    )
    period_date = models.DateField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'portal_hub_income_record'
        verbose_name = 'Hub Income Record'
        verbose_name_plural = 'Hub Income Records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service_code', 'period_date']),
        ]

    def __str__(self):
        return f"{self.service_code} {self.amount} @ {self.created_at}"


class ServiceIncomeConfig(models.Model):
    """
    Hub income config: BBPS, Voucher (what we earn from vendor/ product).
    Rate per txn or percentage for reporting and P&L.
    """
    INCOME_TYPE_CHOICES = [
        ('COMMISSION', 'Commission'),
        ('MARKUP', 'Markup'),
        ('PER_TXN', 'Per Transaction'),
    ]
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='income_configs',
        limit_choices_to={'code__in': ['BBPS', 'VOUCHER', 'GIFT_VOUCHER']},
    )
    income_type = models.CharField(max_length=20, choices=INCOME_TYPE_CHOICES, default='COMMISSION')
    rate_per_txn = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text='Fixed amount per transaction (INR)'
    )
    rate_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Percentage of transaction amount'
    )
    vendor_code = models.CharField(max_length=50, blank=True, null=True, help_text='e.g. mobikwik')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_service_income_config'
        verbose_name = 'Service Income Config'
        verbose_name_plural = 'Service Income Configs'
        ordering = ['service', 'vendor_code']

    def __str__(self):
        return f"{self.service.code} {self.income_type} {self.rate_per_txn or self.rate_percentage}"


class BBPSOperator(models.Model):
    """
    BBPS operator/biller from Operators.xlsx – used by Mobikwik and Euronet.
    Bharat Bill services use this list for categories, fetch bill, and pay.
    """
    # Identity (Biller ID is unique per operator)
    biller_id = models.CharField(
        max_length=100,
        db_index=True,
        unique=True,
        help_text="Biller ID (from Operators.xlsx)"
    )
    # Mobikwik API expects 'op' as integer
    op = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text="Mobikwik operator id (op) – numeric string or int"
    )
    name = models.CharField(max_length=255, help_text="Operator / Biller name")
    category = models.CharField(
        max_length=80,
        db_index=True,
        help_text="Category e.g. ELECTRICITY, WATER, DTH"
    )
    # View Bill / Fetch Bill
    view_bill = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="ViewBill flag from sheet"
    )
    circle = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Circle (cir) for View Bill / Mobikwik API – from Operators.xlsx Circle/cir column"
    )
    customer_label = models.CharField(
        max_length=100,
        default="Consumer ID",
        help_text="Label for consumer/customer ID field (Name/cn in sheet)"
    )
    regex = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Validation regex for consumer ID"
    )
    # Additional params for bill fetch / pay (ad1–ad4, ad9)
    ad1 = models.CharField(max_length=500, blank=True, null=True)
    ad2 = models.CharField(max_length=500, blank=True, null=True)
    ad3 = models.CharField(max_length=500, blank=True, null=True)
    ad4 = models.CharField(max_length=500, blank=True, null=True)
    ad9 = models.CharField(max_length=500, blank=True, null=True)
    additional_params = models.TextField(
        blank=True,
        null=True,
        help_text="Additional Params for payment API (JSON or text)"
    )
    bbps_enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="BBPS Enabled in sheet (True/1/Yes)"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether operator is active in app"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_bbps_operator"
        verbose_name = "BBPS Operator"
        verbose_name_plural = "BBPS Operators"
        ordering = ["category", "name"]
        indexes = [
            models.Index(fields=["category", "bbps_enabled", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.biller_id})"


class RBIRuleConfiguration(models.Model):
    """
    RBI Rules Configuration model
    Stores RBI compliance rules for services like DMT (sender charged)
    """
    
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='rbi_rules',
        help_text="Service this RBI rule applies to"
    )
    
    rule_name = models.CharField(
        max_length=100,
        help_text="Name of the RBI rule"
    )
    rule_description = models.TextField(
        help_text="Description of the RBI rule"
    )
    
    # Rule Configuration (stored as JSON for flexibility)
    rule_config = models.JSONField(
        default=dict,
        help_text="RBI rule configuration (e.g., {'charges_on': 'sender', 'max_amount': 10000})"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this rule is active"
    )
    effective_from = models.DateTimeField(
        default=timezone.now,
        help_text="When this rule becomes effective"
    )
    effective_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this rule expires (null = never expires)"
    )
    
    # Metadata
    rbi_circular_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="RBI circular/notification reference"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_rbi_rules',
        help_text="User who created this rule"
    )
    
    class Meta:
        db_table = 'portal_rbi_rule_configuration'
        verbose_name = 'RBI Rule Configuration'
        verbose_name_plural = 'RBI Rule Configurations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service', 'is_active']),
            models.Index(fields=['is_active', 'effective_from']),
        ]
    
    def __str__(self):
        return f"{self.service.name} - {self.rule_name}"


# ============================================================================
# TICKET MANAGEMENT SYSTEM MODELS
# ============================================================================

class Department(models.Model):
    """Department model for ticket management"""
    
    name = models.CharField(max_length=100, unique=True, help_text="Department name")
    description = models.TextField(blank=True, null=True, help_text="Department description")
    is_active = models.BooleanField(default=True, help_text="Whether department is active")
    can_view_all_tickets = models.BooleanField(
        default=False,
        help_text="Whether department can view tickets from other departments"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_departments',
        help_text="User who created this department"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portal_department'
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name']),
        ]
    
    def __str__(self):
        return self.name


class Agent(models.Model):
    """Agent model - Links User to Department for ticket assignment"""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='agent_profile',
        help_text="User who is an agent"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='agents',
        help_text="Department this agent belongs to"
    )
    is_available = models.BooleanField(
        default=True,
        help_text="Whether agent is available for new ticket assignments"
    )
    max_tickets = models.IntegerField(
        default=10,
        help_text="Maximum number of tickets agent can handle simultaneously"
    )
    current_tickets = models.IntegerField(
        default=0,
        help_text="Current number of active tickets assigned to agent"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portal_agent'
        verbose_name = 'Agent'
        verbose_name_plural = 'Agents'
        unique_together = ['user', 'department']
        indexes = [
            models.Index(fields=['department', 'is_available']),
            models.Index(fields=['is_available', 'current_tickets']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.department.name}"
    
    def can_accept_ticket(self) -> bool:
        """Check if agent can accept a new ticket"""
        return self.is_available and self.current_tickets < self.max_tickets


class Ticket(models.Model):
    """Ticket model - Core ticket management"""
    
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('PENDING', 'Pending'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('REOPENED', 'Reopened'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    ticket_id = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Unique ticket identifier (e.g., TKT-20260125-001)"
    )
    subject = models.CharField(max_length=255, help_text="Ticket subject")
    description = models.TextField(help_text="Detailed ticket description")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW',
        db_index=True,
        help_text="Current ticket status"
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='MEDIUM',
        db_index=True,
        help_text="Ticket priority level"
    )
    category = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Ticket category"
    )
    
    # Relationships
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_tickets',
        help_text="User who created this ticket"
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        help_text="Agent assigned to this ticket"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        help_text="Department handling this ticket"
    )
    
    # Tags for categorization
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of tags for ticket categorization"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'portal_ticket'
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['priority', '-created_at']),
            models.Index(fields=['department', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['created_by', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.ticket_id} - {self.subject}"
    
    def save(self, *args, **kwargs):
        """Override save to auto-generate ticket_id if not set"""
        if not self.ticket_id:
            self.ticket_id = self.generate_ticket_id()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_ticket_id() -> str:
        """Generate unique ticket ID"""
        from django.utils import timezone
        from datetime import datetime
        import random
        
        date_str = timezone.now().strftime('%Y%m%d')
        # Try to find a unique ticket ID
        max_attempts = 100
        for _ in range(max_attempts):
            random_suffix = f"{random.randint(1000, 9999):04d}"
            ticket_id = f"TKT-{date_str}-{random_suffix}"
            if not Ticket.objects.filter(ticket_id=ticket_id).exists():
                return ticket_id
        # Fallback: use timestamp if all attempts fail
        timestamp = int(timezone.now().timestamp())
        return f"TKT-{date_str}-{timestamp % 10000:04d}"
    
    def assign_to_agent(self, agent: User, assigned_by: User = None) -> None:
        """Assign ticket to an agent"""
        self.assigned_to = agent
        self.status = 'OPEN' if self.status == 'NEW' else self.status
        self.save()
        
        # Update agent's current ticket count
        if hasattr(agent, 'agent_profile'):
            agent_profile = agent.agent_profile.first() if hasattr(agent.agent_profile, 'first') else None
            if agent_profile:
                agent_profile.current_tickets = agent.assigned_tickets.filter(
                    status__in=['NEW', 'OPEN', 'IN_PROGRESS', 'PENDING']
                ).count()
                agent_profile.save()
        
        # Create assignment history
        TicketAssignmentHistory.objects.create(
            ticket=self,
            assigned_from=None,
            assigned_to=agent,
            assigned_by=assigned_by or agent,
            reason="Initial assignment"
        )
    
    def update_status(self, new_status: str, updated_by: User) -> None:
        """Update ticket status with timestamp tracking"""
        old_status = self.status
        self.status = new_status
        
        if new_status == 'RESOLVED' and not self.resolved_at:
            from django.utils import timezone
            self.resolved_at = timezone.now()
        elif new_status == 'CLOSED' and not self.closed_at:
            from django.utils import timezone
            self.closed_at = timezone.now()
        elif new_status == 'REOPENED':
            self.resolved_at = None
            self.closed_at = None
        
        self.save()
        
        # Create activity note
        TicketNote.objects.create(
            ticket=self,
            created_by=updated_by,
            content=f"Status changed from {old_status} to {new_status}",
            is_internal=True
        )


# ---------------------------------------------------------------------------
# ParkPe Connect – Vehicle & QR (Phase 1)
# ---------------------------------------------------------------------------


class Vehicle(models.Model):
    """
    Vehicle registered by a user for ParkPe Connect.
    One QR per vehicle; owner can be contacted via masked call/chat/ticket.

    connect_scope splits **personal Connect** (consumer app) from **fleet workspace**:
    same User may have separate rows per scope — they never appear in the other product surface.
    """
    SCOPE_CONSUMER = "consumer"
    SCOPE_FLEET = "fleet"
    CONNECT_SCOPE_CHOICES = [
        (SCOPE_CONSUMER, "Consumer Connect (personal)"),
        (SCOPE_FLEET, "Fleet workspace"),
    ]
    VEHICLE_TYPE_CHOICES = [
        ('', ''),
        ('two_wheeler', 'Bike/Scooty'),
        ('four_wheeler', 'Private Car'),
        ('commercial', 'Commercial'),
    ]
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='connect_vehicles',
        help_text='Owner of the vehicle',
    )
    connect_scope = models.CharField(
        max_length=16,
        choices=CONNECT_SCOPE_CHOICES,
        default=SCOPE_CONSUMER,
        db_index=True,
        help_text='consumer = personal Connect app; fleet = fleet ops only (no mixing in APIs)',
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        blank=True,
        default='',
        db_index=True,
        help_text='Bike/Scooty, Private Car, or Commercial (auto/taxi/big vehicle)',
    )
    registration_number = models.CharField(
        max_length=32,
        db_index=True,
        help_text='Vehicle registration number',
    )
    registration_number_normalized = models.CharField(
        max_length=32,
        blank=True,
        default='',
        db_index=True,
        help_text='Uppercased registration without spaces for indexed lookups',
    )
    brand = models.CharField(max_length=64, blank=True, default='')
    model = models.CharField(max_length=64, blank=True, default='')
    year = models.PositiveIntegerField(null=True, blank=True)
    photo = models.ImageField(
        upload_to='connect/vehicles/',
        blank=True,
        null=True,
        help_text='Optional vehicle photo',
    )
    is_primary = models.BooleanField(
        default=False,
        help_text='Primary vehicle for this user',
    )
    fastag_biller_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_index=True,
        help_text='BBPS FASTag biller id (from Mobikwik/BBPSOperator); user-selected issuer',
    )
    fastag_balance_last_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Last FASTag balance from BBPS View Bill (fetch_bill)',
    )
    fastag_balance_fetched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When fastag_balance_last_value was last refreshed',
    )
    ownership_declaration_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When user accepted the vehicle ownership declaration (audit trail)',
    )
    rc_view_paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When owner paid from voucher (Rs 50) to view full RC; once set, RC is shown without verify',
    )
    rc_view_debit_reference_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text='Voucher redemption / ParkPe DEBIT reference_id for RC_VIEW payment (for refunds and audit)',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_connect_vehicle'
        verbose_name = 'Connect Vehicle'
        verbose_name_plural = 'Connect Vehicles'
        ordering = ['-is_primary', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'registration_number', 'connect_scope'],
                name='portal_connect_vehicle_user_reg_scope_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.registration_number} ({self.user_id})"

    def save(self, *args, **kwargs):
        self.registration_number_normalized = "".join((self.registration_number or "").strip().upper().split())
        if self.is_primary:
            Vehicle.objects.filter(user=self.user, connect_scope=self.connect_scope).exclude(pk=self.pk).update(
                is_primary=False
            )
        super().save(*args, **kwargs)


class VehicleQRCode(models.Model):
    """
    Unique QR code for a Connect vehicle. One active QR per vehicle.
    Scanner uses this code to resolve vehicle and show contact options.
    """
    vehicle = models.OneToOneField(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='qr_code',
        help_text='Vehicle this QR belongs to',
    )
    code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text='Unique slug/code used in QR and URL',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'portal_connect_vehicle_qrcode'
        verbose_name = 'Connect Vehicle QR Code'
        verbose_name_plural = 'Connect Vehicle QR Codes'

    def __str__(self):
        return f"QR {self.code} ({self.vehicle_id})"


class VehicleRCData(models.Model):
    """
    Cached Cashfree Vehicle RC (Registration Certificate) response for a Connect vehicle.
    Fetched automatically when vehicle is created; used for View more details / RC info.
    """
    vehicle = models.OneToOneField(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='rc_data',
        help_text='Vehicle this RC data belongs to',
    )
    raw_response = models.JSONField(
        default=dict,
        help_text='Full Cashfree vehicle-rc API response',
    )
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'portal_connect_vehicle_rc_data'
        verbose_name = 'Vehicle RC Data'
        verbose_name_plural = 'Vehicle RC Data'

    def __str__(self):
        return f"RC data for vehicle {self.vehicle_id}"


class VehicleRCUnlock(models.Model):
    """
    Temporary unlock for viewing RC data when profile name does not match RC owner.
    User verifies with owner name + chassis + engine; unlock expires after 15 minutes.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='connect_vehicle_rc_unlocks',
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='rc_unlocks',
    )
    expires_at = models.DateTimeField(help_text='Unlock valid until this time')

    class Meta:
        db_table = 'portal_connect_vehicle_rc_unlock'
        verbose_name = 'Vehicle RC Unlock'
        verbose_name_plural = 'Vehicle RC Unlocks'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'vehicle'],
                name='portal_connect_vehicle_rc_unlock_user_vehicle_unique',
            ),
        ]

    def __str__(self):
        return f"RC unlock for user {self.user_id} vehicle {self.vehicle_id}"


class ConnectPredefinedMessage(models.Model):
    """Admin-configurable quick message for Connect chat (e.g. Wrong parking, Please move)."""
    code = models.CharField(max_length=64, unique=True, db_index=True)
    label_en = models.CharField(max_length=128, help_text='Button label (English)')
    label_hi = models.CharField(max_length=128, blank=True, default='')
    body_en = models.TextField(help_text='Message text sent (English)')
    body_hi = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    order = models.PositiveSmallIntegerField(default=0, db_index=True)

    class Meta:
        db_table = 'portal_connect_predefined_message'
        verbose_name = 'Connect Predefined Message'
        verbose_name_plural = 'Connect Predefined Messages'
        ordering = ['order', 'code']

    def __str__(self):
        return f"{self.code} ({self.label_en})"


class ConnectThread(models.Model):
    """One chat thread per scanner–vehicle (owner) pair."""
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='connect_threads',
    )
    scanner_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='connect_scanner_threads',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    owner_last_read_message_id = models.PositiveBigIntegerField(default=0, db_index=True)
    scanner_last_read_message_id = models.PositiveBigIntegerField(default=0, db_index=True)
    owner_pinned = models.BooleanField(default=False, db_index=True)
    scanner_pinned = models.BooleanField(default=False, db_index=True)
    owner_muted = models.BooleanField(default=False, db_index=True)
    scanner_muted = models.BooleanField(default=False, db_index=True)
    owner_archived = models.BooleanField(default=False, db_index=True)
    scanner_archived = models.BooleanField(default=False, db_index=True)
    owner_last_seen_at = models.DateTimeField(null=True, blank=True)
    scanner_last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'portal_connect_thread'
        verbose_name = 'Connect Thread'
        verbose_name_plural = 'Connect Threads'
        constraints = [
            models.UniqueConstraint(
                fields=['vehicle', 'scanner_user'],
                name='portal_connect_thread_vehicle_scanner_unique',
            ),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f"Thread vehicle={self.vehicle_id} scanner={self.scanner_user_id}"


class ConnectMessage(models.Model):
    """Single message in a Connect chat thread."""
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('predefined', 'Predefined'),
        ('attachment', 'Attachment'),
        ('voice', 'Voice'),
    ]
    DELIVERY_STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('seen', 'Seen'),
        ('failed', 'Failed'),
    ]
    thread = models.ForeignKey(
        ConnectThread,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='connect_messages_sent',
    )
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text', db_index=True)
    body = models.TextField(help_text='Message content (for predefined, stored resolved body)')
    metadata = models.JSONField(default=dict, blank=True)
    client_id = models.CharField(max_length=80, blank=True, default='', db_index=True)
    delivery_status = models.CharField(max_length=16, choices=DELIVERY_STATUS_CHOICES, default='sent', db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    seen_at = models.DateTimeField(null=True, blank=True)
    predefined_message = models.ForeignKey(
        ConnectPredefinedMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'portal_connect_message'
        verbose_name = 'Connect Message'
        verbose_name_plural = 'Connect Messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['thread', 'created_at']),
        ]

    def __str__(self):
        return f"Msg {self.id} thread={self.thread_id} from {self.sender_id}"


class ConnectCallLog(models.Model):
    """Log of each call initiate for analytics and admin."""
    qr_code = models.CharField(max_length=128, blank=True, default='', db_index=True)
    vehicle_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    scanner_phone_masked = models.CharField(max_length=32, blank=True, default='')
    owner_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    success = models.BooleanField(default=False, db_index=True)
    kaleyra_call_id = models.CharField(
        max_length=128,
        blank=True,
        default='',
        db_index=True,
        help_text='Call ID returned by Kaleyra click-to-call API for cross-referencing with vendor logs',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'portal_connect_call_log'
        verbose_name = 'Connect Call Log'
        verbose_name_plural = 'Connect Call Logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Call {self.id} qr={self.qr_code[:16]}… success={self.success}"


class ConnectScanLog(models.Model):
    """Log of every QR scan for analytics."""
    qr_code = models.CharField(max_length=128, db_index=True)
    vehicle = models.ForeignKey(
        'Vehicle', # Lazy reference to avoid circular imports if any, though likely in same file
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='connect_scans'
    )
    scanned_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='connect_scans_performed'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'portal_connect_scan_log'
        verbose_name = 'Connect Scan Log'
        verbose_name_plural = 'Connect Scan Logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Scan {self.id} on {self.created_at}"


class ConnectQrOnboardLog(models.Model):
    """Log when a user completes Connect QR onboarding (new user flag + vehicle link)."""

    qr_code = models.CharField(max_length=128, db_index=True)
    is_new_user = models.BooleanField(default=False, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="connect_qr_onboard_logs",
    )
    vehicle = models.ForeignKey(
        "Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="connect_qr_onboard_logs",
    )

    class Meta:
        db_table = "portal_connect_qr_onboard_log"
        verbose_name = "Connect QR Onboard Log"
        verbose_name_plural = "Connect QR Onboard Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "qr_code"], name="portal_conn_created_2c353c_idx"),
        ]

    def __str__(self):
        return f"QR onboard {self.id} {self.qr_code[:16]}… user={self.user_id}"


class ConnectReport(models.Model):
    """User report (e.g. from chat) – can be linked to a Ticket."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
    ]
    reporter_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='connect_reports_made',
    )
    reported_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='connect_reports_against',
    )
    thread = models.ForeignKey(
        ConnectThread,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports',
    )
    reason = models.TextField(help_text='Reason or description')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    ticket = models.ForeignKey(
        'Ticket',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='connect_reports',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'portal_connect_report'
        verbose_name = 'Connect Report'
        verbose_name_plural = 'Connect Reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"Report {self.id} by {self.reporter_user_id} vs {self.reported_user_id} ({self.status})"


class ConnectModerationAction(models.Model):
    """Hub-side moderation audit trail for Connect users and incidents."""
    ACTION_WARN = "warn"
    ACTION_TEMP_BLOCK = "temp_block"
    ACTION_PERM_BLOCK = "perm_block"
    ACTION_UNBLOCK = "unblock"
    ACTION_CHOICES = [
        (ACTION_WARN, "Warn"),
        (ACTION_TEMP_BLOCK, "Temporary Block"),
        (ACTION_PERM_BLOCK, "Permanent Block"),
        (ACTION_UNBLOCK, "Unblock"),
    ]

    actor_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="connect_moderation_actions_taken",
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="connect_moderation_actions_received",
    )
    action = models.CharField(max_length=24, choices=ACTION_CHOICES, db_index=True)
    reason = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_connect_moderation_action"
        verbose_name = "Connect Moderation Action"
        verbose_name_plural = "Connect Moderation Actions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_user", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        return f"ConnectModerationAction {self.action} target={self.target_user_id}"


class UserSettingsAuditLog(models.Model):
    SOURCE_HUB = "hub"
    SOURCE_PARKPE = "parkpe"
    SOURCE_SYSTEM = "system"
    SOURCE_CHOICES = [
        (SOURCE_HUB, "Hub"),
        (SOURCE_PARKPE, "ParkPe"),
        (SOURCE_SYSTEM, "System"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="settings_audit_logs",
    )
    actor_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settings_audit_logs_actor",
    )
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_SYSTEM, db_index=True)
    action = models.CharField(max_length=80, db_index=True)
    change_summary = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_user_settings_audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["source", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        return f"UserSettingsAuditLog user={self.user_id} source={self.source} action={self.action}"


class TicketNote(models.Model):
    """Ticket note model - Internal and customer-visible notes"""
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='notes',
        help_text="Ticket this note belongs to"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ticket_notes',
        help_text="User who created this note"
    )
    content = models.TextField(help_text="Note content")
    is_internal = models.BooleanField(
        default=False,
        help_text="Whether this note is internal (not visible to customer)"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'portal_ticket_note'
        verbose_name = 'Ticket Note'
        verbose_name_plural = 'Ticket Notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket', '-created_at']),
            models.Index(fields=['is_internal', '-created_at']),
        ]
    
    def __str__(self):
        return f"Note for {self.ticket.ticket_id} by {self.created_by.username}"


class TicketAssignmentHistory(models.Model):
    """Ticket assignment history - Track all ticket assignments"""
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='assignment_history',
        help_text="Ticket being assigned"
    )
    assigned_from = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_from',
        help_text="Previous agent (if reassignment)"
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_to',
        help_text="New agent assigned"
    )
    reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for assignment/reassignment"
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ticket_assignments',
        help_text="User who performed the assignment"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'portal_ticket_assignment_history'
        verbose_name = 'Ticket Assignment History'
        verbose_name_plural = 'Ticket Assignment Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket', '-created_at']),
            models.Index(fields=['assigned_to', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.ticket.ticket_id} assigned to {self.assigned_to.username if self.assigned_to else 'Unassigned'}"


class TicketAttachment(models.Model):
    """Ticket attachment model - File attachments for tickets"""
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="Ticket this attachment belongs to"
    )
    file = models.FileField(
        upload_to='ticket_attachments/%Y/%m/%d/',
        help_text="Uploaded file"
    )
    file_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original file name"
    )
    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes"
    )
    file_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="File MIME type"
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ticket_attachments',
        help_text="User who uploaded this file"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'portal_ticket_attachment'
        verbose_name = 'Ticket Attachment'
        verbose_name_plural = 'Ticket Attachments'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['ticket', '-uploaded_at']),
        ]
    
    def __str__(self):
        return f"Attachment for {self.ticket.ticket_id} - {self.file_name or self.file.name}"
    
    def save(self, *args, **kwargs):
        """Override save to extract file metadata"""
        if self.file and not self.file_name:
            self.file_name = self.file.name
        if self.file:
            try:
                self.file_size = self.file.size
                import mimetypes
                self.file_type = mimetypes.guess_type(self.file.name)[0] or 'application/octet-stream'
            except (OSError, IOError, AttributeError, ValueError) as e:
                logger.warning(
                    'Could not extract file metadata for TicketAttachment (file=%s): %s',
                    getattr(self.file, 'name', None),
                    e,
                    exc_info=True
                )
        super().save(*args, **kwargs)


# ============================================================================
# GIFT VOUCHER MANAGEMENT MODELS
# ============================================================================

class GiftVoucherBrand(models.Model):
    """Brand model for gift voucher issuance"""
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    ONBOARDING_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    BUSINESS_TYPE_CHOICES = [
        ('LLP', 'Limited Liability Partnership'),
        ('PRIVATE_LTD', 'Private Limited'),
        ('PUBLIC_LTD', 'Public Limited'),
        ('PARTNERSHIP', 'Partnership'),
        ('SOLE_PROPRIETORSHIP', 'Sole Proprietorship'),
        ('HUF', 'Hindu Undivided Family'),
        ('OTHER', 'Other'),
    ]
    
    brand_code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Unique brand identifier code"
    )
    api_identifier = models.CharField(
        max_length=6,
        unique=True,
        db_index=True,
        blank=True,
        null=True,
        help_text="6-char alphanumeric unique code for API; brand isi code se identify hota hai. Auto-generate on save."
    )
    brand_name = models.CharField(
        max_length=255,
        help_text="Brand name"
    )
    business_reg_no = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Business registration number"
    )
    contact_person = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Contact person name"
    )
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Contact email address"
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Contact phone number"
    )
    address = models.TextField(
        blank=True,
        null=True,
        help_text="Business address"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='INACTIVE',  # Changed to INACTIVE - will be ACTIVE after onboarding approval
        db_index=True,
        help_text="Brand status"
    )
    
    # ============================================================================
    # ONBOARDING STATUS & TRACKING
    # ============================================================================
    onboarding_status = models.CharField(
        max_length=20,
        choices=ONBOARDING_STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        help_text="Brand onboarding status"
    )
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When onboarding was completed and approved"
    )
    onboarding_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_brands',
        help_text="Admin user who approved the onboarding"
    )
    onboarding_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Admin notes during onboarding review"
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for onboarding rejection"
    )
    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When onboarding was rejected"
    )
    
    # ============================================================================
    # EXTENDED BUSINESS INFORMATION
    # ============================================================================
    business_type = models.CharField(
        max_length=30,
        choices=BUSINESS_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text="Type of business entity"
    )
    gst_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="GSTIN (GST Number)"
    )
    pan_number = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="PAN (Permanent Account Number)"
    )
    
    # ============================================================================
    # BANKING INFORMATION (Encrypted)
    # ============================================================================
    bank_account_number = models.TextField(
        blank=True,
        null=True,
        help_text="Encrypted bank account number"
    )
    bank_ifsc_code = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        help_text="Bank IFSC code"
    )
    bank_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Bank name"
    )
    account_holder_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Bank account holder name"
    )
    
    # ============================================================================
    # AGREEMENT & TERMS
    # ============================================================================
    agreement_signed = models.BooleanField(
        default=False,
        help_text="Whether agreement has been signed"
    )
    agreement_signed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When agreement was signed"
    )
    terms_accepted = models.BooleanField(
        default=False,
        help_text="Whether terms and conditions have been accepted"
    )
    terms_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When terms were accepted"
    )
    
    # ============================================================================
    # DOCUMENT STORAGE (S3 URLs)
    # ============================================================================
    business_registration_doc = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 URL for business registration document"
    )
    pan_document = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 URL for PAN document"
    )
    gst_certificate = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 URL for GST certificate"
    )
    bank_statement = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 URL for bank statement"
    )
    agreement_document = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 URL for signed agreement document"
    )
    other_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="List of other document S3 URLs with metadata"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_voucher_brands',
        help_text="User who created this brand"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_voucher_brands',
        help_text="User who last updated this brand"
    )
    
    class Meta:
        db_table = 'portal_gift_voucher_brand'
        verbose_name = 'Gift Voucher Brand'
        verbose_name_plural = 'Gift Voucher Brands'
        ordering = ['brand_name']
        indexes = [
            models.Index(fields=['brand_code']),
            models.Index(fields=['status']),
            models.Index(fields=['onboarding_status']),
            models.Index(fields=['status', 'onboarding_status']),
        ]
    
    def __str__(self):
        return f"{self.brand_name} ({self.brand_code})"
    
    def save(self, *args, **kwargs):
        """Auto-generate brand_code and api_identifier if not provided"""
        if not self.brand_code and self.brand_name:
            # Generate code from name: uppercase, replace spaces with underscores
            base_code = self.brand_name.upper().replace(' ', '_')[:15]
            counter = 1
            brand_code = base_code
            while GiftVoucherBrand.objects.filter(brand_code=brand_code).exclude(pk=self.pk).exists():
                brand_code = f"{base_code}_{counter}"
                counter += 1
            self.brand_code = brand_code
        if not self.api_identifier:
            self.api_identifier = self._generate_api_identifier()
        super().save(*args, **kwargs)

    def _generate_api_identifier(self):
        """Generate 6-char alphanumeric unique code (A-Z, 0-9) for API brand identification"""
        import random
        import string
        # Uppercase + digits only to avoid 0/O, 1/l confusion; 36^6 combinations
        chars = string.ascii_uppercase + string.digits
        for _ in range(100):
            code = ''.join(random.SystemRandom().choice(chars) for _ in range(6))
            if not GiftVoucherBrand.objects.filter(api_identifier=code).exists():
                return code
        # Fallback with more attempts (exclude similar chars if needed)
        raise ValueError("Could not generate unique api_identifier")
    
    # ============================================================================
    # ONBOARDING METHODS
    # ============================================================================
    
    def is_onboarded(self) -> bool:
        """Check if brand onboarding is complete and approved"""
        return self.onboarding_status == 'APPROVED'
    
    def can_issue_vouchers(self) -> bool:
        """Check if brand can issue vouchers (must be APPROVED and ACTIVE)"""
        return self.is_onboarded() and self.status == 'ACTIVE'
    
    def submit_for_approval(self):
        """Mark brand onboarding as submitted for admin review"""
        self.onboarding_status = 'SUBMITTED'
        self.save(update_fields=['onboarding_status', 'updated_at'])
    
    def approve_onboarding(self, approved_by):
        """Approve brand onboarding"""
        from django.utils import timezone
        self.onboarding_status = 'APPROVED'
        self.status = 'ACTIVE'  # Activate brand upon approval
        self.onboarding_completed_at = timezone.now()
        self.onboarding_approved_by = approved_by
        self.save(update_fields=[
            'onboarding_status', 'status', 'onboarding_completed_at',
            'onboarding_approved_by', 'updated_at'
        ])
    
    def reject_onboarding(self, approved_by, reason: str):
        """Reject brand onboarding with reason"""
        from django.utils import timezone
        self.onboarding_status = 'REJECTED'
        self.status = 'INACTIVE'
        self.rejection_reason = reason
        self.rejected_at = timezone.now()
        self.onboarding_approved_by = approved_by
        self.save(update_fields=[
            'onboarding_status', 'status', 'rejection_reason', 'rejected_at',
            'onboarding_approved_by', 'updated_at'
        ])
    
    def set_encrypted_bank_account(self, account_number: str):
        """Set encrypted bank account number"""
        if account_number:
            self.bank_account_number = encrypt_data(account_number)
        else:
            self.bank_account_number = None
    
    def get_decrypted_bank_account(self) -> str:
        """Get decrypted bank account number"""
        if self.bank_account_number:
            try:
                return decrypt_data(self.bank_account_number)
            except (ValueError, TypeError) as e:
                logger.warning(
                    'Failed to decrypt bank account for record pk=%s: %s',
                    self.pk,
                    e,
                    exc_info=True
                )
                return ""
        return ""


# ============================================================================
# VOUCHER CLIENT MODEL
# ============================================================================

class VoucherClient(models.Model):
    """Client model for tracking clients under brands"""
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    ]
    
    brand = models.ForeignKey(
        GiftVoucherBrand,
        on_delete=models.CASCADE,
        related_name='clients',
        help_text="Brand this client belongs to"
    )
    client_name = models.CharField(
        max_length=255,
        help_text="Client name"
    )
    client_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique client identifier code"
    )
    contact_person = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Contact person name"
    )
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Contact email address"
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Contact phone number"
    )
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Is this the default Payswap client for the brand"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True,
        help_text="Client status"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_voucher_clients',
        help_text="User who created this client"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When client was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When client was last updated"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional client-specific data"
    )
    
    class Meta:
        db_table = 'portal_voucher_client'
        verbose_name = 'Voucher Client'
        verbose_name_plural = 'Voucher Clients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client_code']),
            models.Index(fields=['brand', 'status']),
            models.Index(fields=['brand', 'is_default']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['brand', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_client_per_brand'
            )
        ]
    
    def __str__(self):
        return f"{self.client_name} ({self.brand.brand_name})"
    
    def save(self, *args, **kwargs):
        # Auto-generate client_code if not provided
        if not self.client_code:
            from portal.utils.voucher_utils import generate_client_code
            self.client_code = generate_client_code(self.brand, self.client_name)
        super().save(*args, **kwargs)


class GiftVoucher(models.Model):
    """Gift voucher model"""
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PARTIALLY_REDEEMED', 'Partially Redeemed'),
        ('FULLY_REDEEMED', 'Fully Redeemed'),
        ('BLOCKED', 'Blocked'),
        ('EXPIRED', 'Expired'),
    ]
    
    ISSUER_TYPE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('API_PARTNER', 'API Partner'),
        ('BRAND_OWNER', 'Brand Owner'),
    ]
    
    brand = models.ForeignKey(
        GiftVoucherBrand,
        on_delete=models.PROTECT,
        related_name='vouchers',
        help_text="Brand that issued this voucher"
    )
    client = models.ForeignKey(
        'VoucherClient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vouchers',
        help_text="Client this voucher was issued for"
    )
    reference_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique reference number for tracking"
    )
    voucher_code = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        help_text="16-digit unique voucher code (display format: XXXX-XXXX-XXXX-XXXX)"
    )
    voucher_code_hash = models.CharField(
        max_length=255,
        help_text="Encrypted voucher code for storage"
    )
    pin_hash = models.CharField(
        max_length=255,
        help_text="Hashed PIN (bcrypt)"
    )
    original_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Original voucher amount"
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Current available balance"
    )
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Currency code"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True,
        help_text="Voucher status"
    )
    mobile_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        db_index=True,
        help_text="Mobile number for OTP-based redemption"
    )
    pin_retry_count = models.IntegerField(
        default=0,
        help_text="Number of failed PIN attempts"
    )
    pin_blocked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp until which PIN is blocked"
    )
    last_pin_change = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last PIN change"
    )
    pin_history = models.JSONField(
        default=list,
        blank=True,
        help_text="Hash of last 3 PINs (JSON array)"
    )
    issued_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When voucher was issued"
    )
    last_transaction_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last transaction"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_vouchers',
        help_text="User who created this voucher"
    )
    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_vouchers',
        help_text="User who issued this voucher (Admin/API Partner/Brand Owner)"
    )
    issuer_type = models.CharField(
        max_length=20,
        choices=ISSUER_TYPE_CHOICES,
        blank=True,
        null=True,
        db_index=True,
        help_text="Type of issuer (Admin/API Partner/Brand Owner)"
    )
    issuer_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Human-readable issuer name"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional brand-specific data"
    )
    
    class Meta:
        db_table = 'portal_gift_voucher'
        verbose_name = 'Gift Voucher'
        verbose_name_plural = 'Gift Vouchers'
        ordering = ['-issued_at']
        permissions = [
            ('view_voucher_sensitive', 'Can view voucher PIN and sensitive details (e.g. mobile number)'),
        ]
        indexes = [
            models.Index(fields=['voucher_code']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['brand', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['mobile_number']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['issued_by', 'issuer_type']),
            # Phase 2.2: Performance indexes
            models.Index(fields=['brand', 'status', '-issued_at'], name='gv_brand_status_issued_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(current_balance__gte=0),
                name='portal_giftvoucher_current_balance_non_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(original_amount__gte=0),
                name='portal_giftvoucher_original_amount_non_negative',
            ),
        ]

    history = HistoricalRecords(
        inherit=False,
        excluded_fields=[
            'issued_at', 'last_transaction_at',
            'pin_hash', 'pin_history', 'voucher_code_hash',
        ],
        user_model=settings.AUTH_USER_MODEL,
    )
    
    def __str__(self):
        return f"Voucher {self.voucher_code} - {self.brand.brand_name} - {self.current_balance} {self.currency}"


class GiftVoucherTransaction(models.Model):
    """Voucher transaction model - Records all voucher operations"""
    
    TRANSACTION_TYPE_CHOICES = [
        ('ISSUANCE', 'Issuance'),
        ('REDEMPTION', 'Redemption'),
        ('BALANCE_INQUIRY', 'Balance Inquiry'),
        ('PIN_CHANGE', 'PIN Change'),
    ]
    
    REDEMPTION_METHOD_CHOICES = [
        ('PIN', 'PIN'),
        ('OTP', 'OTP'),
    ]
    
    TRANSACTION_STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending'),
    ]
    
    voucher = models.ForeignKey(
        GiftVoucher,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text="Voucher this transaction belongs to"
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        db_index=True,
        help_text="Type of transaction"
    )
    transaction_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Transaction amount (NULL for inquiry/PIN change)"
    )
    balance_before = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Balance before transaction"
    )
    balance_after = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Balance after transaction"
    )
    redemption_method = models.CharField(
        max_length=10,
        choices=REDEMPTION_METHOD_CHOICES,
        null=True,
        blank=True,
        help_text="Redemption method used (for redemption transactions)"
    )
    transaction_status = models.CharField(
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        help_text="Transaction status"
    )
    failure_reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Failure reason if transaction failed"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="User agent string"
    )
    transaction_ref = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="External transaction reference (unique)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When transaction was created"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional transaction metadata"
    )
    
    class Meta:
        db_table = 'portal_gift_voucher_transaction'
        verbose_name = 'Gift Voucher Transaction'
        verbose_name_plural = 'Gift Voucher Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['voucher', '-created_at']),
            models.Index(fields=['transaction_type', '-created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['transaction_ref']),
            # Phase 2.2: Performance index (already exists but ensuring it's there)
        ]
    
    def __str__(self):
        return f"{self.transaction_type} - {self.voucher.voucher_code} - {self.transaction_status}"


class GiftVoucherOTP(models.Model):
    """OTP records for voucher operations"""
    
    OTP_PURPOSE_CHOICES = [
        ('REDEMPTION', 'Redemption'),
        ('PIN_CHANGE', 'PIN Change'),
    ]
    
    voucher = models.ForeignKey(
        GiftVoucher,
        on_delete=models.CASCADE,
        related_name='otp_records',
        help_text="Voucher this OTP belongs to"
    )
    mobile_number = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Mobile number OTP was sent to"
    )
    otp_hash = models.CharField(
        max_length=255,
        help_text="Hashed OTP (bcrypt)"
    )
    otp_purpose = models.CharField(
        max_length=20,
        choices=OTP_PURPOSE_CHOICES,
        help_text="Purpose of OTP"
    )
    attempt_count = models.IntegerField(
        default=0,
        help_text="Number of verification attempts"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether OTP has been verified"
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When OTP was generated"
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="When OTP expires"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When OTP was verified"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    
    class Meta:
        db_table = 'portal_gift_voucher_otp'
        verbose_name = 'Gift Voucher OTP'
        verbose_name_plural = 'Gift Voucher OTPs'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['voucher', '-generated_at']),
            models.Index(fields=['mobile_number']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"OTP for {self.voucher.voucher_code} - {self.otp_purpose} - {'Verified' if self.is_verified else 'Pending'}"


class BulkVoucherIssuanceBatch(models.Model):
    """Bulk voucher issuance batch model"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    ISSUANCE_METHOD_CHOICES = [
        ('FILE_UPLOAD', 'File Upload'),
        ('MANUAL_BULK', 'Manual Bulk'),
    ]
    
    ISSUER_TYPE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('API_PARTNER', 'API Partner'),
        ('BRAND_OWNER', 'Brand Owner'),
    ]
    
    brand = models.ForeignKey(
        GiftVoucherBrand,
        on_delete=models.PROTECT,
        related_name='bulk_batches',
        help_text="Brand for this batch"
    )
    client = models.ForeignKey(
        'VoucherClient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bulk_batches',
        help_text="Client this batch was issued for"
    )
    batch_reference = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique batch reference number"
    )
    batch_reference_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        blank=True,
        null=True,
        help_text="Additional batch reference number"
    )
    total_vouchers = models.IntegerField(
        help_text="Total number of vouchers in batch"
    )
    processed_vouchers = models.IntegerField(
        default=0,
        help_text="Number of vouchers processed"
    )
    successful_vouchers = models.IntegerField(
        default=0,
        help_text="Number of successfully created vouchers"
    )
    failed_vouchers = models.IntegerField(
        default=0,
        help_text="Number of failed voucher creations"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        help_text="Batch processing status"
    )
    uploaded_file_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Path to uploaded file (S3 or local)"
    )
    result_file_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Path to result file (S3 or local)"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When batch processing started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When batch processing completed"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When batch was created"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_voucher_batches',
        help_text="User who created this batch"
    )
    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_voucher_batches',
        help_text="User who issued this batch (Admin/API Partner/Brand Owner)"
    )
    processing_locked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When batch processing was locked/started"
    )
    processing_locked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='locked_voucher_batches',
        help_text="User who initiated processing (lock holder)"
    )
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Celery task ID for tracking processing task"
    )
    issuer_type = models.CharField(
        max_length=20,
        choices=ISSUER_TYPE_CHOICES,
        blank=True,
        null=True,
        db_index=True,
        help_text="Type of issuer (Admin/API Partner/Brand Owner)"
    )
    issuance_method = models.CharField(
        max_length=20,
        choices=ISSUANCE_METHOD_CHOICES,
        default='FILE_UPLOAD',
        db_index=True,
        help_text="Method used for issuance (File Upload or Manual Bulk)"
    )
    denomination_breakdown = models.JSONField(
        default=dict,
        blank=True,
        help_text="Multi-denomination breakdown: {amount: quantity, successful, failed}"
    )
    error_log = models.TextField(
        blank=True,
        null=True,
        help_text="Error log for failed processing"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Batch processing metadata including voucher progress tracking"
    )
    
    class Meta:
        db_table = 'portal_bulk_voucher_issuance_batch'
        verbose_name = 'Bulk Voucher Issuance Batch'
        verbose_name_plural = 'Bulk Voucher Issuance Batches'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['batch_reference']),
            models.Index(fields=['batch_reference_number']),
            models.Index(fields=['brand', 'status']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['issued_by', 'issuer_type']),
            models.Index(fields=['issuance_method']),
            # Phase 2.2: Performance index for status queries
            models.Index(fields=['status', '-created_at'], name='bulkbatch_status_created_idx'),
        ]
    
    def __str__(self):
        return f"Batch {self.batch_reference} - {self.brand.brand_name} - {self.status}"


class GiftVoucherAuditLog(models.Model):
    """Audit log for gift voucher operations"""
    
    entity_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of entity (brand, voucher, transaction, etc.)"
    )
    entity_id = models.BigIntegerField(
        db_index=True,
        help_text="ID of the entity"
    )
    action = models.CharField(
        max_length=100,
        help_text="Action performed"
    )
    user_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="User ID who performed the action"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="User agent string"
    )
    old_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Old values before change"
    )
    new_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="New values after change"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When audit log was created"
    )
    
    class Meta:
        db_table = 'portal_gift_voucher_audit_log'
        verbose_name = 'Gift Voucher Audit Log'
        verbose_name_plural = 'Gift Voucher Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user_id']),
        ]
    
    def __str__(self):
        return f"{self.action} - {self.entity_type} #{self.entity_id} - {self.created_at}"


# ============================================================================
# RESELLER PARTNER SYSTEM MODELS
# ============================================================================

class ResellerPartner(models.Model):
    """
    Reseller Partner model for API access management
    Partners can be onboarded and given API access to services
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('REJECTED', 'Rejected'),
    ]
    
    ONBOARDING_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    BUSINESS_TYPE_CHOICES = [
        ('LLP', 'Limited Liability Partnership'),
        ('PRIVATE_LTD', 'Private Limited'),
        ('PUBLIC_LTD', 'Public Limited'),
        ('PARTNERSHIP', 'Partnership'),
        ('SOLE_PROPRIETORSHIP', 'Sole Proprietorship'),
        ('HUF', 'Hindu Undivided Family'),
        ('OTHER', 'Other'),
    ]
    
    partner_code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Auto-generated partner identifier code"
    )
    company_name = models.CharField(
        max_length=255,
        help_text="Business/Company name"
    )
    contact_person = models.CharField(
        max_length=255,
        help_text="Primary contact person name"
    )
    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="Business email address"
    )
    phone = models.CharField(
        max_length=20,
        help_text="Contact phone number"
    )
    business_type = models.CharField(
        max_length=50,
        choices=BUSINESS_TYPE_CHOICES,
        help_text="Type of business entity"
    )
    gst_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="GST registration number (optional)"
    )
    address = models.TextField(
        help_text="Business address"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        help_text="Partner status"
    )
    onboarding_status = models.CharField(
        max_length=20,
        choices=ONBOARDING_STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        help_text="Onboarding status"
    )
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When onboarding was completed and approved"
    )
    onboarding_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_reseller_partners',
        help_text="Admin user who approved the onboarding"
    )
    onboarding_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Admin notes during onboarding review"
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reseller_partners',
        help_text="Partner wallet for transactions"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional partner data and configuration"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_reseller_partners',
        help_text="User who created this partner record"
    )
    
    history = HistoricalRecords(
        inherit=False,
        excluded_fields=['created_at', 'updated_at'],
        user_model=settings.AUTH_USER_MODEL,
    )

    class Meta:
        db_table = 'portal_reseller_partner'
        verbose_name = 'Reseller Partner'
        verbose_name_plural = 'Reseller Partners'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['partner_code']),
            models.Index(fields=['email']),
            models.Index(fields=['status', 'onboarding_status']),
            models.Index(fields=['onboarding_status', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.company_name} ({self.partner_code})"
    
    def save(self, *args, **kwargs):
        # Auto-generate partner_code if not provided
        if not self.partner_code:
            from portal.utils.user_utils import generate_username
            self.partner_code = 'PRT' + generate_username('P')[:8]
        super().save(*args, **kwargs)
    
    def can_issue_vouchers(self):
        """Check if partner can issue vouchers (approved and active)"""
        return self.status == 'ACTIVE' and self.onboarding_status == 'APPROVED'


class PartnerVendorAssignment(models.Model):
    """
    Maps which vendors a partner can use for each service.
    Admin assigns specific vendors to partners; requests are routed to assigned vendor.
    """
    partner = models.ForeignKey(
        ResellerPartner,
        on_delete=models.CASCADE,
        related_name='vendor_assignments',
        help_text="Reseller partner"
    )
    service_code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Service code: bbps, aeps, dmt, kyc, sms, payment, voucher"
    )
    vendor = models.ForeignKey(
        ApiVendor,
        on_delete=models.CASCADE,
        related_name='partner_assignments',
        help_text="API vendor assigned for this service"
    )
    is_primary = models.BooleanField(
        default=True,
        help_text="Primary vendor for this service (used when no vendor specified)"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.IntegerField(
        default=1,
        help_text="Order for fallback routing (lower = higher priority)"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_partner_vendors',
        help_text="Admin who made the assignment"
    )

    class Meta:
        db_table = 'portal_partner_vendor_assignment'
        verbose_name = 'Partner Vendor Assignment'
        verbose_name_plural = 'Partner Vendor Assignments'
        unique_together = [['partner', 'service_code', 'vendor']]
        ordering = ['service_code', 'priority']

    def __str__(self):
        return f"{self.partner.company_name} - {self.service_code} -> {self.vendor.name}"


class APIKey(models.Model):
    """
    API Key model for Reseller Partner authentication
    Stores hashed API keys with service-level permissions
    """
    
    KEY_TYPE_CHOICES = [
        ('LIVE', 'Live'),
        ('TEST', 'Test'),
        ('SANDBOX', 'Sandbox'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('REVOKED', 'Revoked'),
        ('EXPIRED', 'Expired'),
    ]
    
    partner = models.ForeignKey(
        ResellerPartner,
        on_delete=models.CASCADE,
        related_name='api_keys',
        help_text="Reseller partner this API key belongs to"
    )
    key_name = models.CharField(
        max_length=100,
        help_text="User-friendly name for this API key"
    )
    api_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Hashed API key (never store plain text)"
    )
    api_secret = models.CharField(
        max_length=255,
        help_text="Hashed secret for HMAC signing"
    )
    key_prefix = models.CharField(
        max_length=20,
        help_text="Key prefix for identification (e.g., 'psk_live_')"
    )
    key_type = models.CharField(
        max_length=20,
        choices=KEY_TYPE_CHOICES,
        default='LIVE',
        db_index=True,
        help_text="Type of API key"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True,
        help_text="API key status"
    )
    permissions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Service-level permissions"
    )
    rate_limit = models.JSONField(
        default=dict,
        blank=True,
        help_text="Per-service rate limits"
    )
    ip_whitelist = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed IP addresses (empty list = allow all)"
    )
    webhook_url = models.URLField(
        blank=True,
        null=True,
        help_text="Webhook URL for notifications"
    )
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Webhook secret for signature verification"
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this API key was used"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Expiration date (null = never expires)"
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this key was revoked"
    )
    revoked_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for revocation"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_api_keys',
        help_text="User who created this API key"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    history = HistoricalRecords(
        inherit=False,
        excluded_fields=[
            'created_at', 'updated_at', 'last_used_at',
            'api_key', 'api_secret', 'webhook_secret',
        ],
        user_model=settings.AUTH_USER_MODEL,
    )

    class Meta:
        db_table = 'portal_api_key'
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['api_key']),
            models.Index(fields=['partner', 'status']),
            models.Index(fields=['key_type', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.key_name} - {self.partner.company_name} ({self.key_type})"
    
    def is_active(self):
        """Check if API key is active and not expired"""
        if self.status != 'ACTIVE':
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
    
    def has_permission(self, service, action):
        """Check if API key has permission for service and action"""
        if not self.is_active():
            return False
        service_perms = self.permissions.get(service, {})
        return service_perms.get(action, False)
    
    def is_ip_allowed(self, ip_address):
        """Check if IP address is in whitelist"""
        if not self.ip_whitelist:
            return True  # Empty whitelist = allow all
        return ip_address in self.ip_whitelist


class InternalAPIKey(models.Model):
    """
    DEPRECATED: Use ResellerPartner + APIKey instead. ParkPe and other apps are
    treated as first-class partners (e.g. ResellerPartner partner_code='parkpe')
    with API keys. This model is retained for backward compatibility only; do not
    use for new partner identity. See Payswap API Governance Platform plan.
    API keys for internal apps (Payswap, Parkpe).
    Links an app to an APIKey; internal apps use same auth as partners.
    """
    app_name = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="App identifier: payswap, parkpe"
    )
    description = models.TextField(blank=True)
    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.CASCADE,
        related_name='internal_app_bindings',
        help_text="API key used by this app"
    )
    environment = models.CharField(
        max_length=20,
        default='production',
        help_text="development, staging, production"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_internal_api_keys',
        help_text="User who last updated this record"
    )

    class Meta:
        db_table = 'portal_internal_api_key'
        verbose_name = 'Internal API Key'
        verbose_name_plural = 'Internal API Keys'
        ordering = ['app_name']

    def __str__(self):
        return f"{self.app_name} ({self.environment})"


class APIKeyUsageLog(models.Model):
    """
    API Key usage log for analytics and monitoring
    Tracks all API requests made with API keys
    """
    
    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.CASCADE,
        related_name='usage_logs',
        help_text="API key used for this request"
    )
    partner = models.ForeignKey(
        ResellerPartner,
        on_delete=models.CASCADE,
        related_name='api_usage_logs',
        help_text="Reseller partner who made this request"
    )
    endpoint = models.CharField(
        max_length=200,
        db_index=True,
        help_text="API endpoint called"
    )
    method = models.CharField(
        max_length=10,
        help_text="HTTP method (GET, POST, etc.)"
    )
    status_code = models.IntegerField(
        db_index=True,
        help_text="HTTP status code"
    )
    response_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Response time in milliseconds"
    )
    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text="IP address of the request"
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="User agent string"
    )
    request_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Request ID for tracing"
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if request failed"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this request was made"
    )
    
    class Meta:
        db_table = 'portal_api_key_usage_log'
        verbose_name = 'API Key Usage Log'
        verbose_name_plural = 'API Key Usage Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['api_key', '-created_at']),
            models.Index(fields=['partner', '-created_at']),
            models.Index(fields=['endpoint', '-created_at']),
            models.Index(fields=['status_code', '-created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code} - {self.created_at}"


# ============================================================================
# RESELLER PARTNER PRICING & COMMISSION MODELS
# ============================================================================

class ResellerPartnerPricing(models.Model):
    """
    Pricing and commission structure for reseller partners per service
    Each partner can have different pricing for each service
    """
    
    PRICING_TYPE_CHOICES = [
        ('PERCENTAGE', 'Percentage'),
        ('FIXED', 'Fixed Amount'),
        ('TIERED', 'Tiered Pricing'),
    ]
    
    COMMISSION_TYPE_CHOICES = [
        ('REVENUE_SHARE', 'Revenue Share'),
        ('MARKUP', 'Markup'),
        ('FIXED_COMMISSION', 'Fixed Commission'),
    ]
    
    partner = models.ForeignKey(
        ResellerPartner,
        on_delete=models.CASCADE,
        related_name='pricing_configs',
        help_text="Reseller partner"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='partner_pricing',
        help_text="Service this pricing applies to"
    )
    vendor = models.ForeignKey(
        ApiVendor,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='partner_pricing',
        help_text="Vendor-specific pricing (null = default for service)"
    )
    
    # Pricing Configuration
    pricing_type = models.CharField(
        max_length=20,
        choices=PRICING_TYPE_CHOICES,
        default='PERCENTAGE',
        help_text="Type of pricing model"
    )
    base_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Base price for the service"
    )
    markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Markup percentage (if pricing_type is PERCENTAGE)"
    )
    fixed_markup = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Fixed markup amount (if pricing_type is FIXED)"
    )
    
    # Commission Configuration
    commission_type = models.CharField(
        max_length=20,
        choices=COMMISSION_TYPE_CHOICES,
        default='REVENUE_SHARE',
        help_text="Type of commission model"
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Commission percentage (if commission_type is REVENUE_SHARE)"
    )
    fixed_commission = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Fixed commission amount (if commission_type is FIXED_COMMISSION)"
    )
    
    # Tiered Pricing (stored as JSON)
    tiered_pricing = models.JSONField(
        default=list,
        blank=True,
        help_text="Tiered pricing structure: [{'min': 0, 'max': 1000, 'rate': 2.5}, ...]"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this pricing is active"
    )
    effective_from = models.DateTimeField(
        default=timezone.now,
        help_text="When this pricing becomes effective"
    )
    effective_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this pricing expires (null = never expires)"
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes about this pricing configuration"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_partner_pricing',
        help_text="User who created this pricing"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    history = HistoricalRecords(
        inherit=False,
        excluded_fields=['created_at', 'updated_at'],
        user_model=settings.AUTH_USER_MODEL,
    )

    class Meta:
        db_table = 'portal_reseller_partner_pricing'
        verbose_name = 'Reseller Partner Pricing'
        verbose_name_plural = 'Reseller Partner Pricing'
        unique_together = [['partner', 'service', 'vendor']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['partner', 'service', 'is_active']),
            models.Index(fields=['is_active', 'effective_from']),
            models.Index(fields=['partner', 'service', 'vendor']),
        ]
        constraints = [
            # Only one default (vendor=null) pricing per partner+service
            models.UniqueConstraint(
                fields=['partner', 'service'],
                condition=models.Q(vendor__isnull=True),
                name='portal_reseller_partner_pricing_unique_default',
            ),
        ]
    
    def __str__(self):
        return f"{self.partner.company_name} - {self.service.name} Pricing"
    
    def calculate_price(self, base_amount):
        """
        Calculate final price for partner based on pricing configuration
        
        Args:
            base_amount: Base amount for the service
        
        Returns:
            Final price after markup
        """
        if self.pricing_type == 'PERCENTAGE':
            return base_amount + (base_amount * self.markup_percentage / 100)
        elif self.pricing_type == 'FIXED':
            return base_amount + self.fixed_markup
        elif self.pricing_type == 'TIERED':
            # Calculate based on tiered pricing
            for tier in self.tiered_pricing:
                if tier.get('min', 0) <= base_amount <= tier.get('max', float('inf')):
                    rate = tier.get('rate', 0)
                    if tier.get('type') == 'percentage':
                        return base_amount + (base_amount * rate / 100)
                    else:
                        return base_amount + rate
            return base_amount
        return base_amount
    
    def calculate_commission(self, transaction_amount):
        """
        Calculate commission for partner based on commission configuration
        
        Args:
            transaction_amount: Transaction amount
        
        Returns:
            Commission amount
        """
        if self.commission_type == 'REVENUE_SHARE':
            return transaction_amount * self.commission_percentage / 100
        elif self.commission_type == 'MARKUP':
            # Markup is already included in price, commission is the markup
            if self.pricing_type == 'PERCENTAGE':
                return transaction_amount * self.markup_percentage / 100
            else:
                return self.fixed_markup
        elif self.commission_type == 'FIXED_COMMISSION':
            return self.fixed_commission
        return Decimal('0.00')


class ResellerPartnerTransaction(models.Model):
    """
    Financial transactions for reseller partners
    Records all revenue, commission, and settlement transactions
    """
    
    TRANSACTION_TYPE_CHOICES = [
        ('REVENUE', 'Revenue'),
        ('COMMISSION', 'Commission'),
        ('SETTLEMENT', 'Settlement'),
        ('ADJUSTMENT', 'Adjustment'),
        ('REFUND', 'Refund'),
        ('CHARGEBACK', 'Chargeback'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    partner = models.ForeignKey(
        ResellerPartner,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text="Reseller partner"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='partner_transactions',
        help_text="Service this transaction is for"
    )
    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        help_text="API key used for this transaction"
    )
    
    # Transaction Details
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        db_index=True,
        help_text="Type of transaction"
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Transaction amount"
    )
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Currency code"
    )
    
    # Commission Details
    commission_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Commission earned by partner"
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Commission rate used"
    )
    
    # Pricing Details
    base_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Base amount before markup"
    )
    markup_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Markup amount"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        help_text="Transaction status"
    )
    
    # Reference Information
    reference_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Reference ID (e.g., voucher code, payment ID)"
    )
    external_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="External reference (e.g., partner's transaction ID)"
    )
    
    # Metadata
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Transaction description"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional transaction data"
    )
    
    # Timestamps
    transaction_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Transaction date/time"
    )
    settled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When transaction was settled"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_partner_transactions',
        help_text="User who created this transaction"
    )
    
    class Meta:
        db_table = 'portal_reseller_partner_transaction'
        verbose_name = 'Reseller Partner Transaction'
        verbose_name_plural = 'Reseller Partner Transactions'
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['partner', 'transaction_type', '-transaction_date']),
            models.Index(fields=['partner', 'status', '-transaction_date']),
            models.Index(fields=['service', '-transaction_date']),
            models.Index(fields=['transaction_date']),
            models.Index(fields=['reference_id']),
        ]
        # DB-enforced: at most one REVENUE per (partner, reference_id) when reference_id set.
        # Prevents double-debit under concurrent charge_partner_for_service with same reference_id.
        constraints = [
            models.UniqueConstraint(
                fields=["partner", "reference_id"],
                condition=models.Q(transaction_type="REVENUE") & ~models.Q(reference_id__isnull=True) & ~models.Q(reference_id=""),
                name="partner_revenue_reference_id_unique",
            )
        ]

    history = HistoricalRecords(
        inherit=False,
        excluded_fields=['created_at', 'updated_at'],
        user_model=settings.AUTH_USER_MODEL,
    )

    def __str__(self):
        return f"{self.partner.company_name} - {self.transaction_type} - {self.amount} {self.currency}"


class ResellerPartnerSettlement(models.Model):
    """
    Settlement records for reseller partners
    Tracks periodic settlements of commissions and revenue
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    partner = models.ForeignKey(
        ResellerPartner,
        on_delete=models.CASCADE,
        related_name='settlements',
        help_text="Reseller partner"
    )
    
    # Settlement Period
    settlement_period_start = models.DateTimeField(
        help_text="Start of settlement period"
    )
    settlement_period_end = models.DateTimeField(
        help_text="End of settlement period"
    )
    
    # Financial Summary
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Total revenue in period"
    )
    total_commission = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Total commission earned"
    )
    total_transactions = models.IntegerField(
        default=0,
        help_text="Total number of transactions"
    )
    settlement_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Amount to be settled"
    )
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Currency code"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        help_text="Settlement status"
    )
    
    # Settlement Details
    settlement_reference = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        help_text="Settlement reference number"
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Payment method (NEFT, IMPS, UPI, etc.)"
    )
    payment_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Payment reference number"
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Settlement notes"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional settlement data"
    )
    
    # Timestamps
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When settlement was processed"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When settlement was completed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_settlements',
        help_text="User who created this settlement"
    )
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_settlements',
        help_text="User who processed this settlement"
    )
    
    history = HistoricalRecords(
        inherit=False,
        excluded_fields=['created_at', 'updated_at'],
        user_model=settings.AUTH_USER_MODEL,
    )

    class Meta:
        db_table = 'portal_reseller_partner_settlement'
        verbose_name = 'Reseller Partner Settlement'
        verbose_name_plural = 'Reseller Partner Settlements'
        ordering = ['-settlement_period_end', '-created_at']
        indexes = [
            models.Index(fields=['partner', 'status', '-settlement_period_end']),
            models.Index(fields=['status', '-settlement_period_end']),
            models.Index(fields=['settlement_reference']),
        ]
    
    def __str__(self):
        return f"{self.partner.company_name} - Settlement {self.settlement_period_start.date()} to {self.settlement_period_end.date()} - {self.settlement_amount} {self.currency}"


# ============================================================================
# IDEMPOTENCY (Financial API safety – 24h TTL)
# ============================================================================

class IdempotencyRecord(models.Model):
    """
    Strong idempotency: reserve key at request start (PENDING), only one request
    executes business logic; complete with response or mark FAILED.
    Scope = (partner_id + endpoint). Same key returns stored response when COMPLETED.
    """
    STATUS_PENDING = "PENDING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    scope = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Scope: e.g. partner_123:v2:voucher_issue"
    )
    idempotency_key = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Client-provided idempotency key (header or body)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        help_text="PENDING=reserved, COMPLETED=stored response, FAILED=error"
    )
    response_http_status = models.IntegerField(
        null=True,
        blank=True,
        help_text="Stored response HTTP status (set when status=COMPLETED)"
    )
    response_body = models.TextField(
        null=True,
        blank=True,
        help_text="Stored response body (JSON) to return on replay when COMPLETED"
    )
    request_fingerprint = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 fingerprint of normalized request payload for key reuse validation"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_idempotency_record"
        verbose_name = "Idempotency Record"
        verbose_name_plural = "Idempotency Records"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "idempotency_key"],
                name="portal_idempotency_scope_key_unique",
            )
        ]
        indexes = [
            models.Index(fields=["scope", "idempotency_key"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.scope}:{self.idempotency_key[:16]}..."


# ============================================================================
# INSTANTPAY TRANSACTIONS (Hub reconciliation store)
# ============================================================================

class InstantpayTransaction(models.Model):
    STATUS_INITIATED = "initiated"
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_REVERSED = "reversed"
    STATUS_CHOICES = [
        (STATUS_INITIATED, "Initiated"),
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REVERSED, "Reversed"),
    ]

    partner = models.ForeignKey(
        'ResellerPartner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instantpay_transactions",
    )
    vendor = models.ForeignKey(
        ApiVendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instantpay_transactions",
    )
    service_name = models.CharField(max_length=64, db_index=True)
    action = models.CharField(max_length=64, db_index=True)
    partner_txn_id = models.CharField(max_length=128, db_index=True)
    vendor_reference = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    idempotency_key = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED, db_index=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_instantpay_transaction"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["partner_txn_id"]),
            models.Index(fields=["service_name", "action"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["partner", "partner_txn_id"],
                name="portal_instantpay_partner_txn_unique",
            )
        ]

    def __str__(self):
        return f"{self.partner_txn_id} ({self.status})"


# ============================================================================
# FLEET WORKSPACE — user interest before admin assigns fleet role
# ============================================================================

class FleetWorkspaceInterest(models.Model):
    """
    Consumer taps Fleet in ParkPe → submits interest. Ops approves in Django admin
    and we assign a fleet role (default fleet_operator) on the User.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fleet_workspace_interests",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    company_name = models.CharField(max_length=200, blank=True, default="")
    message = models.TextField(blank=True, default="")
    assigned_role_code = models.CharField(
        max_length=40,
        default="fleet_operator",
        help_text="Role code applied to the user when this request is approved in admin.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fleet_interests_reviewed",
    )
    rejection_reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "portal_fleet_workspace_interest"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"FleetInterest({self.user_id}, {self.status})"


class FleetDriverRoster(models.Model):
    """
    Fleet admin/manager → drivers they may register vehicles for.
    Operators/dispatchers manage only their own vehicles unless promoted.
    """

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fleet_roster_managed",
        db_index=True,
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fleet_roster_memberships",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_fleet_driver_roster"
        constraints = [
            models.UniqueConstraint(
                fields=["manager", "driver"],
                name="uniq_portal_fleet_roster_manager_driver",
            ),
        ]
        indexes = [
            models.Index(fields=["manager", "driver"]),
        ]

    def __str__(self):
        return f"FleetRoster(m={self.manager_id}, d={self.driver_id})"


# ============================================================================
# APPROVAL WORKFLOW (4-eye / maker-checker for high-risk admin actions)
# ============================================================================

class ApprovalRequest(models.Model):
    """
    Generic approval request for high-risk actions. Enforces 4-eye: requester
    creates PENDING; only a different user with sufficient role can APPROVE
    or REJECT. Execution happens ONLY after APPROVE, via existing services.
    Payload is immutable once created (do not update after save).
    """
    ACTION_TYPE_CHOICES = [
        ('partner_wallet_credit', 'Partner Wallet Credit'),
        ('partner_wallet_debit', 'Partner Wallet Debit'),
        ('settlement_execute', 'Settlement Execute / Mark Paid'),
        ('refund_execute', 'Refund Execution'),
        ('voucher_status_override', 'Voucher Status Override (Block/Cancel)'),
        ('manual_balance_adjustment', 'Manual Wallet/Voucher Balance Adjustment'),
    ]
    ENTITY_TYPE_CHOICES = [
        ('wallet', 'Wallet'),
        ('settlement', 'Settlement'),
        ('voucher', 'Voucher'),
        ('payment', 'Payment'),
    ]
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    action_type = models.CharField(
        max_length=64,
        choices=ACTION_TYPE_CHOICES,
        db_index=True,
        help_text="High-risk action that requires approval"
    )
    entity_type = models.CharField(
        max_length=32,
        choices=ENTITY_TYPE_CHOICES,
        db_index=True,
        help_text="Type of entity (wallet, settlement, voucher, payment)"
    )
    entity_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="ID of the entity (e.g. partner id, settlement id, voucher id)"
    )
    # Minimal data needed to execute; MUST NOT contain secrets. Immutable after create.
    payload = models.JSONField(
        default=dict,
        help_text="Minimal data to execute (amount, reference_id, reason, etc.). Do not store secrets."
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approval_requests_created",
        help_text="User who requested the action (maker)"
    )
    requested_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the request was created (UTC)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        help_text="PENDING=awaiting approval, APPROVED=executed, REJECTED=denied, EXPIRED=timed out"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approval_requests_approved",
        help_text="User who approved or rejected (checker)"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the request was approved or rejected (UTC)"
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for rejection if status=REJECTED"
    )
    # Audit: result of execution (e.g. transaction id, settlement ref) for APPROVED
    execution_result = models.JSONField(
        default=dict,
        blank=True,
        help_text="Result of execution (transaction_id, etc.) for audit"
    )

    history = HistoricalRecords(
        inherit=False,
        excluded_fields=['requested_at'],
        user_model=settings.AUTH_USER_MODEL,
    )

    class Meta:
        db_table = "portal_approval_request"
        verbose_name = "Approval Request"
        verbose_name_plural = "Approval Requests"
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["status", "action_type"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        return f"{self.action_type} #{self.id} ({self.status})"


# ============================================================================
# NOTIFICATION BANNERS (Hub-managed communication slots for ParkPe/Payswap)
# ============================================================================

class NotificationBanner(models.Model):
    PLATFORM_BOTH = "both"
    PLATFORM_PARKPE = "parkpe"
    PLATFORM_PAYSWAP = "payswap"
    PLATFORM_CHOICES = [
        (PLATFORM_BOTH, "Both"),
        (PLATFORM_PARKPE, "ParkPe"),
        (PLATFORM_PAYSWAP, "Payswap"),
    ]

    SLOT_BBPS_RIGHT_RAIL = "bbps_right_rail"
    SLOT_DASHBOARD_TOP = "dashboard_top"
    SLOT_SERVICE_INLINE = "service_inline"
    SLOT_CHOICES = [
        (SLOT_BBPS_RIGHT_RAIL, "BBPS Right Rail"),
        (SLOT_DASHBOARD_TOP, "Dashboard Top"),
        (SLOT_SERVICE_INLINE, "Service Inline"),
    ]

    name = models.CharField(max_length=120, db_index=True)
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=320)
    cta_text = models.CharField(max_length=48, blank=True, default="")
    cta_url = models.CharField(max_length=255, blank=True, default="")
    image_url = models.CharField(max_length=255, blank=True, default="")
    bg_color = models.CharField(max_length=16, blank=True, default="#1f4f94")
    text_color = models.CharField(max_length=16, blank=True, default="#ffffff")
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES, default=PLATFORM_BOTH, db_index=True)
    slot = models.CharField(max_length=32, choices=SLOT_CHOICES, default=SLOT_BBPS_RIGHT_RAIL, db_index=True)
    service_code = models.CharField(max_length=48, blank=True, default="", db_index=True)
    screen_code = models.CharField(max_length=64, blank=True, default="", db_index=True)
    priority = models.IntegerField(default=100, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    campaign = models.ForeignKey(
        "NotificationCampaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="banners",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_banners_created",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_notification_banner"
        ordering = ["priority", "-created_at"]
        indexes = [
            models.Index(fields=["platform", "slot", "is_active"]),
            models.Index(fields=["service_code", "screen_code"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.platform}]"


class NotificationCampaign(models.Model):
    TYPE_MANUAL = "manual"
    TYPE_EVENT = "event"
    TYPE_CHOICES = [
        (TYPE_MANUAL, "Manual"),
        (TYPE_EVENT, "Event"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_SCHEDULED = "scheduled"
    STATUS_RUNNING = "running"
    STATUS_PAUSED = "paused"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_RUNNING, "Running"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_COMPLETED, "Completed"),
    ]

    name = models.CharField(max_length=140, db_index=True)
    campaign_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_MANUAL, db_index=True)
    event_key = models.CharField(max_length=80, blank=True, default="", db_index=True)
    description = models.CharField(max_length=320, blank=True, default="")
    channels = models.JSONField(default=list, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_campaigns_created",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_notification_campaign"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["campaign_type", "status"]),
            models.Index(fields=["event_key", "status"]),
        ]

    def __str__(self):
        return self.name


class NotificationAudienceRule(models.Model):
    campaign = models.ForeignKey(
        NotificationCampaign,
        on_delete=models.CASCADE,
        related_name="audience_rules",
    )
    platform = models.CharField(max_length=16, choices=NotificationBanner.PLATFORM_CHOICES, default=NotificationBanner.PLATFORM_BOTH, db_index=True)
    service_code = models.CharField(max_length=48, blank=True, default="", db_index=True)
    screen_code = models.CharField(max_length=64, blank=True, default="", db_index=True)
    role_code = models.CharField(max_length=40, blank=True, default="", db_index=True)
    user_ids = models.JSONField(default=list, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_notification_audience_rule"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["platform", "service_code", "screen_code"]),
        ]

    def __str__(self):
        return f"Audience[{self.campaign_id}] {self.platform}"


class NotificationMessageTemplate(models.Model):
    CHANNEL_IN_APP = "in_app"
    CHANNEL_PUSH = "push"
    CHANNEL_SMS = "sms"
    CHANNEL_EMAIL = "email"
    CHANNEL_BANNER = "banner"
    CHANNEL_CHOICES = [
        (CHANNEL_IN_APP, "In-App"),
        (CHANNEL_PUSH, "Push"),
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_BANNER, "Banner"),
    ]

    campaign = models.ForeignKey(
        NotificationCampaign,
        on_delete=models.CASCADE,
        related_name="templates",
    )
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES, db_index=True)
    subject = models.CharField(max_length=160, blank=True, default="")
    title = models.CharField(max_length=160, blank=True, default="")
    body = models.TextField(blank=True, default="")
    cta_text = models.CharField(max_length=64, blank=True, default="")
    cta_url = models.CharField(max_length=255, blank=True, default="")
    image_url = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_notification_message_template"
        ordering = ["channel", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "channel"],
                name="portal_notification_template_campaign_channel_unique",
            )
        ]

    def __str__(self):
        return f"{self.campaign_id}:{self.channel}"


class DevicePushToken(models.Model):
    PLATFORM_IOS = "ios"
    PLATFORM_ANDROID = "android"
    PLATFORM_WEB = "web"
    DEVICE_PLATFORM_CHOICES = [
        (PLATFORM_IOS, "iOS"),
        (PLATFORM_ANDROID, "Android"),
        (PLATFORM_WEB, "Web"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_push_tokens",
    )
    token = models.CharField(max_length=512, unique=True)
    device_platform = models.CharField(max_length=16, choices=DEVICE_PLATFORM_CHOICES, default=PLATFORM_ANDROID, db_index=True)
    app_platform = models.CharField(max_length=16, choices=NotificationBanner.PLATFORM_CHOICES, default=NotificationBanner.PLATFORM_PARKPE, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_device_push_token"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["app_platform", "device_platform"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.device_platform}"


class NotificationEventRule(models.Model):
    campaign = models.ForeignKey(
        NotificationCampaign,
        on_delete=models.CASCADE,
        related_name="event_rules",
    )
    event_key = models.CharField(max_length=80, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.IntegerField(default=100, db_index=True)
    condition_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_notification_event_rule"
        ordering = ["priority", "-created_at"]
        indexes = [
            models.Index(fields=["event_key", "is_active"]),
        ]

    def __str__(self):
        return f"{self.event_key}:{self.campaign_id}"


class UserNotification(models.Model):
    CHANNEL_CHOICES = NotificationMessageTemplate.CHANNEL_CHOICES

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_notifications",
    )
    campaign = models.ForeignKey(
        NotificationCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_notifications",
    )
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES, default=NotificationMessageTemplate.CHANNEL_IN_APP, db_index=True)
    title = models.CharField(max_length=180)
    message = models.TextField()
    deep_link = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_user_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.channel}:{self.title[:24]}"


class NotificationDeliveryLog(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_FAILED = "failed"
    STATUS_READ = "read"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_FAILED, "Failed"),
        (STATUS_READ, "Read"),
    ]

    channel = models.CharField(max_length=16, choices=NotificationMessageTemplate.CHANNEL_CHOICES, db_index=True)
    campaign = models.ForeignKey(
        NotificationCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_delivery_logs",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)
    destination = models.CharField(max_length=255, blank=True, default="")
    provider = models.CharField(max_length=64, blank=True, default="")
    provider_message_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_notification_delivery_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["channel", "status", "-created_at"]),
            models.Index(fields=["campaign", "status"]),
        ]

    def __str__(self):
        return f"{self.channel}:{self.status}:{self.provider_message_id or self.id}"


class PasskeyCredential(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="passkey_credentials",
    )
    credential_id = models.CharField(max_length=512, unique=True, db_index=True)
    public_key = models.BinaryField()
    sign_count = models.BigIntegerField(default=0)
    transports = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    label = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "portal_passkey_credential"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.credential_id[:18]}"
