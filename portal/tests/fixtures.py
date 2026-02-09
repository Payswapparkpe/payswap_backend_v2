"""
Test Fixtures and Factories for Portal Tests
Uses factory-boy for generating test data
"""
import factory
from factory.django import DjangoModelFactory
from faker import Faker
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from portal.models import (
    User, Role, Profile,
    GiftVoucherBrand, VoucherClient, GiftVoucher, GiftVoucherTransaction,
    BulkVoucherIssuanceBatch, GiftVoucherOTP,
    Wallet, WalletTransaction,
    Ticket, TicketNote, TicketAttachment,
    Department, Agent, Service, KYC
)

fake = Faker()


# ============================================================
# User and Authentication Fixtures
# ============================================================

class RoleFactory(DjangoModelFactory):
    """Factory for Role model"""
    class Meta:
        model = Role
        django_get_or_create = ('code',)
    
    code = 'ADMIN'
    name = 'Administrator'
    description = 'System Administrator'


class UserFactory(DjangoModelFactory):
    """Factory for User model"""
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'user{n}')
    phone_number = factory.LazyAttribute(lambda o: f'+91{fake.numerify("##########")}')
    role = factory.SubFactory(RoleFactory)
    role_code = factory.LazyAttribute(lambda o: o.role.code)
    is_active = True
    is_staff = False
    is_superuser = False
    mfa_enabled = False


class AdminUserFactory(UserFactory):
    """Factory for Admin users"""
    role = factory.SubFactory(RoleFactory, code='ADMIN', name='Administrator')
    role_code = 'ADMIN'
    is_staff = True


class ProfileFactory(DjangoModelFactory):
    """Factory for Profile model"""
    class Meta:
        model = Profile
    
    user = factory.SubFactory(UserFactory)
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.Faker('email')
    date_of_birth = factory.Faker('date_of_birth', minimum_age=18, maximum_age=80)
    address_line1 = factory.Faker('street_address')
    city = factory.Faker('city')
    state = factory.Faker('state')
    pincode = factory.Faker('zipcode')
    country = 'India'
    is_complete = True


# ============================================================
# Gift Voucher Fixtures
# ============================================================

class GiftVoucherBrandFactory(DjangoModelFactory):
    """Factory for GiftVoucherBrand model"""
    class Meta:
        model = GiftVoucherBrand
    
    brand_name = factory.Sequence(lambda n: f'Brand {n}')
    brand_code = factory.Sequence(lambda n: f'BRD{n:04d}')
    brand_description = factory.Faker('text', max_nb_chars=200)
    brand_logo = factory.django.ImageField(color='blue')
    contact_person = factory.Faker('name')
    contact_email = factory.Faker('company_email')
    contact_phone = factory.LazyAttribute(lambda o: f'+91{fake.numerify("##########")}')
    terms_and_conditions = factory.Faker('text', max_nb_chars=500)
    is_active = True
    min_denomination = Decimal('100.00')
    max_denomination = Decimal('10000.00')
    validity_days = 365
    created_by = factory.SubFactory(AdminUserFactory)
    onboarding_status = 'APPROVED'


class VoucherClientFactory(DjangoModelFactory):
    """Factory for VoucherClient model"""
    class Meta:
        model = VoucherClient
    
    brand = factory.SubFactory(GiftVoucherBrandFactory)
    client_name = factory.Sequence(lambda n: f'Client {n}')
    client_code = factory.Sequence(lambda n: f'CLI{n:05d}')
    contact_person = factory.Faker('name')
    contact_email = factory.Faker('email')
    contact_phone = factory.LazyAttribute(lambda o: f'+91{fake.numerify("##########")}')
    is_active = True
    is_default = False
    created_by = factory.SubFactory(AdminUserFactory)


class GiftVoucherFactory(DjangoModelFactory):
    """Factory for GiftVoucher model"""
    class Meta:
        model = GiftVoucher
    
    brand = factory.SubFactory(GiftVoucherBrandFactory)
    client = factory.SubFactory(VoucherClientFactory)
    voucher_code = factory.Sequence(lambda n: f'{n:016d}')
    amount = Decimal('1000.00')
    balance = factory.LazyAttribute(lambda o: o.amount)
    currency = 'INR'
    status = 'ACTIVE'
    valid_from = factory.LazyFunction(timezone.now)
    valid_until = factory.LazyFunction(lambda: timezone.now() + timedelta(days=365))
    issued_at = factory.LazyFunction(timezone.now)
    issued_by = factory.SubFactory(AdminUserFactory)
    issuer_type = 'ADMIN'
    recipient_mobile = factory.LazyAttribute(lambda o: f'+91{fake.numerify("##########")}')
    recipient_email = factory.Faker('email')


class GiftVoucherTransactionFactory(DjangoModelFactory):
    """Factory for GiftVoucherTransaction model"""
    class Meta:
        model = GiftVoucherTransaction
    
    voucher = factory.SubFactory(GiftVoucherFactory)
    transaction_type = 'REDEMPTION'
    amount = Decimal('500.00')
    balance_before = factory.LazyAttribute(lambda o: o.voucher.balance)
    balance_after = factory.LazyAttribute(lambda o: o.balance_before - o.amount)
    description = 'Test transaction'
    performed_by = factory.SubFactory(UserFactory)


class BulkVoucherIssuanceBatchFactory(DjangoModelFactory):
    """Factory for BulkVoucherIssuanceBatch model"""
    class Meta:
        model = BulkVoucherIssuanceBatch
    
    brand = factory.SubFactory(GiftVoucherBrandFactory)
    client = factory.SubFactory(VoucherClientFactory)
    batch_id = factory.Sequence(lambda n: f'BATCH{n:08d}')
    issuance_type = 'MANUAL'
    total_vouchers = 100
    successful_vouchers = 0
    failed_vouchers = 0
    processed_vouchers = 0
    status = 'PENDING'
    issued_by = factory.SubFactory(AdminUserFactory)
    issuer_type = 'ADMIN'


class GiftVoucherOTPFactory(DjangoModelFactory):
    """Factory for GiftVoucherOTP model"""
    class Meta:
        model = GiftVoucherOTP
    
    voucher = factory.SubFactory(GiftVoucherFactory)
    otp_code = factory.Sequence(lambda n: f'{n:06d}')
    mobile_number = factory.LazyAttribute(lambda o: o.voucher.recipient_mobile)
    purpose = 'REDEMPTION'
    is_verified = False
    attempts = 0
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=10))


# ============================================================
# Wallet Fixtures
# ============================================================

class WalletFactory(DjangoModelFactory):
    """Factory for Wallet model"""
    class Meta:
        model = Wallet
    
    user = factory.SubFactory(UserFactory)
    balance = Decimal('1000.00')
    currency = 'INR'
    is_active = True


class WalletTransactionFactory(DjangoModelFactory):
    """Factory for WalletTransaction model"""
    class Meta:
        model = WalletTransaction
    
    wallet = factory.SubFactory(WalletFactory)
    transaction_type = 'CREDIT'
    amount = Decimal('500.00')
    balance_before = factory.LazyAttribute(lambda o: o.wallet.balance)
    balance_after = factory.LazyAttribute(lambda o: o.balance_before + o.amount)
    description = 'Test transaction'
    reference_id = factory.Sequence(lambda n: f'TXN{n:010d}')
    status = 'COMPLETED'


# ============================================================
# Ticket Management Fixtures
# ============================================================

class DepartmentFactory(DjangoModelFactory):
    """Factory for Department model"""
    class Meta:
        model = Department
    
    name = factory.Sequence(lambda n: f'Department {n}')
    description = factory.Faker('text', max_nb_chars=200)
    is_active = True


class AgentFactory(DjangoModelFactory):
    """Factory for Agent model"""
    class Meta:
        model = Agent
    
    user = factory.SubFactory(UserFactory)
    department = factory.SubFactory(DepartmentFactory)
    is_active = True


class TicketFactory(DjangoModelFactory):
    """Factory for Ticket model"""
    class Meta:
        model = Ticket
    
    ticket_number = factory.Sequence(lambda n: f'TKT{n:08d}')
    subject = factory.Faker('sentence', nb_words=6)
    description = factory.Faker('text', max_nb_chars=500)
    category = 'TECHNICAL'
    priority = 'MEDIUM'
    status = 'OPEN'
    created_by = factory.SubFactory(UserFactory)
    department = factory.SubFactory(DepartmentFactory)


class TicketNoteFactory(DjangoModelFactory):
    """Factory for TicketNote model"""
    class Meta:
        model = TicketNote
    
    ticket = factory.SubFactory(TicketFactory)
    note = factory.Faker('text', max_nb_chars=300)
    is_internal = False
    created_by = factory.SubFactory(UserFactory)


# ============================================================
# Service Management Fixtures
# ============================================================

class ServiceFactory(DjangoModelFactory):
    """Factory for Service model"""
    class Meta:
        model = Service
    
    name = factory.Sequence(lambda n: f'Service {n}')
    code = factory.Sequence(lambda n: f'SRV{n:04d}')
    description = factory.Faker('text', max_nb_chars=200)
    category = 'UTILITY'
    is_active = True
    requires_kyc = False


class KYCFactory(DjangoModelFactory):
    """Factory for KYC model"""
    class Meta:
        model = KYC
    
    user = factory.SubFactory(UserFactory)
    kyc_type = 'AADHAAR'
    kyc_number = factory.Sequence(lambda n: f'{n:012d}')
    status = 'PENDING'
    submitted_at = factory.LazyFunction(timezone.now)


# ============================================================
# Helper Functions
# ============================================================

def create_test_user(role_code='ADMIN', **kwargs):
    """Helper function to create a test user with profile"""
    role, _ = Role.objects.get_or_create(
        code=role_code,
        defaults={'name': role_code.title(), 'description': f'{role_code} role'}
    )
    user = UserFactory(role=role, role_code=role_code, **kwargs)
    ProfileFactory(user=user)
    return user


def create_test_brand_with_client(**kwargs):
    """Helper function to create a brand with a default client"""
    brand = GiftVoucherBrandFactory(**kwargs)
    client = VoucherClientFactory(brand=brand, is_default=True)
    return brand, client


def create_test_voucher_batch(total_vouchers=10, **kwargs):
    """Helper function to create a batch with vouchers"""
    batch = BulkVoucherIssuanceBatchFactory(total_vouchers=total_vouchers, **kwargs)
    vouchers = []
    for i in range(total_vouchers):
        voucher = GiftVoucherFactory(
            brand=batch.brand,
            client=batch.client,
            issued_by=batch.issued_by
        )
        vouchers.append(voucher)
    return batch, vouchers


def create_test_ticket_with_notes(num_notes=3, **kwargs):
    """Helper function to create a ticket with notes"""
    ticket = TicketFactory(**kwargs)
    notes = []
    for i in range(num_notes):
        note = TicketNoteFactory(ticket=ticket)
        notes.append(note)
    return ticket, notes
