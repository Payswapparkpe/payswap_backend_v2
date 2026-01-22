"""
Portal Models - User Management, KYC, Wallet
"""
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from portal.utils.user_utils import generate_username, get_role_prefix, is_mfa_required_role
from portal.utils.encryption import encrypt_data, decrypt_data
from portal.utils.validators import validate_phone_number, validate_pan_number, validate_aadhaar_number


class Profile(models.Model):
    """Profile model - One profile can have multiple users"""
    
    PROFILE_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=PROFILE_TYPE_CHOICES, default='individual')
    business_name = models.CharField(max_length=255, blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True)  # GST, PAN, etc.
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        blank=True,
        null=True
    )
    email = models.EmailField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_profiles'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portal_profile'
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.type})"


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
    """Custom User model with role-based username generation"""
    
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
    
    # Override username to be auto-generated (but can be provided)
    username = models.CharField(
        max_length=20,
        unique=True,
        help_text="Auto-generated username in format [Role]00[6 digits] if not provided"
    )
    
    # Override first_name to make it required
    first_name = models.CharField(
        max_length=150,
        blank=False,
        help_text="Required. User's first name."
    )
    
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True
    )
    
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
        help_text="User role code (required)"
    )
    
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        blank=False,
        help_text="Required. User's mobile number."
    )
    
    # Override email to make it required
    email = models.EmailField(
        blank=False,
        help_text="Required. User's email address."
    )
    
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    
    # KYC fields
    kyc_completed = models.BooleanField(default=False)
    kyc_status = models.CharField(
        max_length=20,
        choices=KYC_STATUS_CHOICES,
        default='not_required'
    )
    
    # MFA fields
    mfa_enabled = models.BooleanField(default=False)
    mfa_configured = models.BooleanField(default=False)
    mfa_method = models.CharField(
        max_length=20,
        choices=MFA_METHOD_CHOICES,
        blank=True,
        null=True
    )
    totp_secret = models.CharField(max_length=32, blank=True, null=True)  # Encrypted
    
    # Security fields
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
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
        from django.core.exceptions import ValidationError
        
        # Validate required fields
        if not self.first_name or not self.first_name.strip():
            raise ValidationError({'first_name': 'First name is required.'})
        
        if not self.email or not self.email.strip():
            raise ValidationError({'email': 'Email is required.'})
        
        if not self.phone or not self.phone.strip():
            raise ValidationError({'phone': 'Mobile number is required.'})
        
        if not self.role_code:
            raise ValidationError({'role_code': 'Role is required.'})
        
        # Auto-generate username if not set
        if not self.username and self.role_code:
            role_prefix = get_role_prefix(self.role_code)
            self.username = generate_username(role_prefix)
    
    def save(self, *args, **kwargs):
        # Auto-generate username if not set
        if not self.username and self.role_code:
            role_prefix = get_role_prefix(self.role_code)
            self.username = generate_username(role_prefix)
        
        # Set role from role_code if role is not set
        if not self.role and self.role_code:
            try:
                self.role = Role.objects.get(code=self.role_code)
            except Role.DoesNotExist:
                pass
        
        # Save first to ensure user exists
        super().save(*args, **kwargs)
        
        # Sync to Django Groups after save
        if self.role:
            from portal.utils.role_utils import sync_user_to_groups
            sync_user_to_groups(self, self.role)
    
    @classmethod
    def create_user(cls, username=None, email=None, password=None, **extra_fields):
        """Override create_user to handle auto-generated username"""
        # Generate username if not provided and role_code is available
        if not username:
            role_code = extra_fields.get('role_code')
            if role_code:
                role_prefix = get_role_prefix(role_code)
                username = generate_username(role_prefix)
            else:
                # Fallback to 'U' prefix if no role_code
                username = generate_username('U')
        return super().create_user(username, email, password, **extra_fields)
    
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
