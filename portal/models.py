"""
Portal Models - User Management, KYC, Wallet
"""
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission, UserManager as BaseUserManager
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from portal.utils.user_utils import generate_username, get_role_prefix, is_mfa_required_role
from portal.utils.encryption import encrypt_data, decrypt_data
from portal.utils.validators import validate_phone_number, validate_pan_number, validate_aadhaar_number


class UserManager(BaseUserManager):
    """Custom UserManager that handles auto-generated usernames"""
    
    def _create_user_object(self, username, email, password, **extra_fields):
        """Override to not set email (email is a property that reads from Profile)"""
        # Remove email from kwargs since it's a property
        extra_fields.pop('email', None)
        # Create user without email
        user = self.model(username=username, **extra_fields)
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
        """Create superuser with auto-generated username if not provided"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(username, password, **extra_fields)


class Profile(models.Model):
    """Profile model - Mandatory OneToOne with User, contains all user details"""
    
    PROFILE_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
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
            except Exception:
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
    
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('employee', 'Employee'),
        ('super', 'Super'),
        ('distributor', 'Distributor'),
        ('retailer', 'Retailer'),
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
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
    email = models.EmailField(blank=True, null=True)  # Email is in Profile, kept for backward compatibility
    
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
    totp_secret = models.CharField(max_length=32, blank=True, null=True)  # Encrypted
    
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
        if self.requires_mfa() and not self.mfa_configured:
            return False
        # Check KYC if required for role
        kyc_required_roles = ['customer', 'vendor', 'distributor', 'retailer']
        if self.role_code in kyc_required_roles and not self.kyc_completed:
            return False
        return True
    
    def get_encrypted_totp_secret(self) -> str:
        """Get decrypted TOTP secret"""
        if self.totp_secret:
            try:
                return decrypt_data(self.totp_secret)
            except Exception:
                return ""
        return ""
    
    def set_encrypted_totp_secret(self, secret: str) -> None:
        """Set encrypted TOTP secret"""
        if secret:
            self.totp_secret = encrypt_data(secret)
        else:
            self.totp_secret = None
    
    # Convenience methods to access profile data
    @property
    def email(self):
        """Get email from profile"""
        return self.profile.email if hasattr(self, 'profile') and self.profile else None
    
    @property
    def phone(self):
        """Get phone from profile"""
        return self.profile.phone if hasattr(self, 'profile') and self.profile else None
    
    @property
    def first_name(self):
        """Get first_name from profile"""
        return self.profile.first_name if hasattr(self, 'profile') and self.profile else None
    
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
    
    def __str__(self):
        return f"Wallet for {self.user.username} - {self.balance} {self.currency}"
    
    def get_decrypted_seed_phrase(self) -> str:
        """Get decrypted seed phrase"""
        if self.encrypted_seed_phrase:
            try:
                return decrypt_data(self.encrypted_seed_phrase)
            except Exception:
                return ""
        return ""
    
    def set_encrypted_seed_phrase(self, seed_phrase: str) -> None:
        """Set encrypted seed phrase"""
        if seed_phrase:
            self.encrypted_seed_phrase = encrypt_data(seed_phrase)
        else:
            self.encrypted_seed_phrase = None


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
        """Revoke permission"""
        self.is_active = False
        self.revoked_at = timezone.now()
        if revoked_by:
            # Could store revoked_by if needed
            pass
        self.save()
