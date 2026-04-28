"""
Parkpe Parking Platform Models
Covers: Location, Zone, Slot, Rate, Booking, Session, Ticket, Transaction, Revenue, Operator
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from portal.utils.logging_helper import get_logger

logger = get_logger("portal.models.parking")

User = settings.AUTH_USER_MODEL


# ─── Location & Slot ────────────────────────────────────────────────────────

class ParkingLocation(models.Model):
    """A parking facility registered in the Hub."""

    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)

    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    # GeoJSON polygon stored as JSON; PostGIS can be added later via migration
    geofence_polygon = models.JSONField(
        default=dict,
        blank=True,
        help_text="GeoJSON polygon of the parking boundary for entry geo-validation",
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_parking_locations",
        help_text="Hub user who owns this parking facility",
    )
    # Link to Hub Project for RBAC scoping
    hub_project_id = models.IntegerField(
        null=True, blank=True,
        help_text="rbac.Project PK — scopes operator assignments",
    )

    total_slots = models.PositiveIntegerField(default=0)
    amenities = models.JSONField(
        default=list,
        blank=True,
        help_text='e.g. ["covered","cctv","ev_charging","valet","toilet"]',
    )
    opening_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"open":"06:00","close":"23:00","247":false}',
    )
    images = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords(inherit=False, user_model=User)

    class Meta:
        db_table = "parking_location"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["city", "is_active"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.name}, {self.city}"

    @property
    def available_slots(self):
        return self.zones.aggregate(
            total=models.Sum(
                models.Case(
                    models.When(slots__status=ParkingSlot.STATUS_AVAILABLE, then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            )
        )["total"] or 0


class ParkingZone(models.Model):
    """A floor/section within a parking location."""

    ZONE_TYPE_2W = "2W"
    ZONE_TYPE_4W = "4W"
    ZONE_TYPE_EV = "EV"
    ZONE_TYPE_VIP = "VIP"
    ZONE_TYPE_HANDICAP = "HANDICAP"
    ZONE_TYPE_HEAVY = "HEAVY"

    ZONE_TYPE_CHOICES = [
        (ZONE_TYPE_2W, "Two Wheeler"),
        (ZONE_TYPE_4W, "Four Wheeler"),
        (ZONE_TYPE_EV, "EV Charging"),
        (ZONE_TYPE_VIP, "VIP"),
        (ZONE_TYPE_HANDICAP, "Handicap"),
        (ZONE_TYPE_HEAVY, "Heavy Vehicle"),
    ]

    location = models.ForeignKey(
        ParkingLocation, on_delete=models.CASCADE, related_name="zones"
    )
    zone_name = models.CharField(max_length=100, help_text='e.g. "Ground Floor", "Zone A"')
    floor_level = models.IntegerField(default=0, help_text="0=Ground, 1=Floor1, -1=Basement1")
    zone_type = models.CharField(max_length=20, choices=ZONE_TYPE_CHOICES, default=ZONE_TYPE_4W)
    total_slots = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "parking_zone"
        ordering = ["floor_level", "display_order", "zone_name"]
        unique_together = [("location", "zone_name")]

    def __str__(self):
        return f"{self.location.name} — {self.zone_name} ({self.zone_type})"


class ParkingSlot(models.Model):
    """Individual parking slot within a zone."""

    STATUS_AVAILABLE = "available"
    STATUS_OCCUPIED = "occupied"
    STATUS_RESERVED = "reserved"
    STATUS_BLOCKED = "blocked"
    STATUS_MAINTENANCE = "maintenance"

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_OCCUPIED, "Occupied"),
        (STATUS_RESERVED, "Reserved"),
        (STATUS_BLOCKED, "Blocked"),
        (STATUS_MAINTENANCE, "Maintenance"),
    ]

    VEHICLE_TYPE_2W = "two_wheeler"
    VEHICLE_TYPE_4W = "four_wheeler"
    VEHICLE_TYPE_EV = "ev"
    VEHICLE_TYPE_HEAVY = "heavy_vehicle"

    VEHICLE_TYPE_CHOICES = [
        (VEHICLE_TYPE_2W, "Two Wheeler"),
        (VEHICLE_TYPE_4W, "Four Wheeler"),
        (VEHICLE_TYPE_EV, "EV"),
        (VEHICLE_TYPE_HEAVY, "Heavy Vehicle"),
    ]

    zone = models.ForeignKey(ParkingZone, on_delete=models.CASCADE, related_name="slots")
    slot_code = models.CharField(max_length=20, help_text='e.g. "A-101", "G-05"')
    vehicle_type = models.CharField(
        max_length=20, choices=VEHICLE_TYPE_CHOICES, default=VEHICLE_TYPE_4W
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    features = models.JSONField(
        default=list,
        blank=True,
        help_text='e.g. ["covered","ev_charging","cctv"]',
    )
    sensor_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text="IoT sensor / RFID tag for automated status updates",
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parking_slot"
        unique_together = [("zone", "slot_code")]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["zone", "status"]),
        ]

    def __str__(self):
        return f"{self.zone.location.name} › {self.zone.zone_name} › {self.slot_code}"

    @property
    def location(self):
        return self.zone.location

    @property
    def rate(self):
        """Current per-hour rate for this slot's vehicle type."""
        rate_obj = ParkingRate.objects.filter(
            location=self.zone.location,
            vehicle_type=self.vehicle_type,
            is_active=True,
        ).first()
        return float(rate_obj.per_hour_rate) if rate_obj else 0.0

    @property
    def currency(self):
        return "INR"


# ─── Pricing ────────────────────────────────────────────────────────────────

class ParkingRate(models.Model):
    """Time-based pricing rules per vehicle type per location."""

    VEHICLE_TYPE_CHOICES = ParkingSlot.VEHICLE_TYPE_CHOICES

    location = models.ForeignKey(
        ParkingLocation, on_delete=models.CASCADE, related_name="rates"
    )
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES)
    base_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
        help_text="Fixed charge on entry (base fee)",
        validators=[MinValueValidator(Decimal("0"))],
    )
    per_hour_rate = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    # First N minutes free grace period
    grace_minutes = models.PositiveSmallIntegerField(default=15)
    daily_cap = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Max charge per day; null = no cap",
    )
    overnight_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Fixed overnight charge (22:00–06:00); null = regular rate",
    )
    weekend_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("1.0"),
        help_text="e.g. 1.5 = 50% extra on weekends",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parking_rate"
        unique_together = [("location", "vehicle_type")]

    def __str__(self):
        return f"{self.location.name} — {self.vehicle_type} ₹{self.per_hour_rate}/hr"

    def estimate(self, duration_minutes: int) -> Decimal:
        """Calculate estimated charge for a given duration."""
        if duration_minutes <= self.grace_minutes:
            return self.base_rate

        billable_minutes = duration_minutes - self.grace_minutes
        hours = Decimal(str(billable_minutes)) / Decimal("60")
        import math
        # Ceil to nearest 30 min slab
        slabs = math.ceil(billable_minutes / 30)
        amount = self.base_rate + (Decimal(str(slabs)) * self.per_hour_rate / Decimal("2"))

        if self.daily_cap and amount > self.daily_cap:
            amount = self.daily_cap

        return amount.quantize(Decimal("0.01"))


# ─── Booking ─────────────────────────────────────────────────────────────────

class ParkingBooking(models.Model):
    """Customer booking record — the core transactional entity."""

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_reference = models.CharField(
        max_length=20, unique=True, db_index=True,
        help_text="Human-readable booking ref e.g. PKP-20240428-0001",
    )
    customer = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="parking_bookings"
    )
    slot = models.ForeignKey(
        ParkingSlot, on_delete=models.PROTECT, related_name="bookings"
    )

    vehicle_number = models.CharField(max_length=20)
    vehicle_type = models.CharField(max_length=20, choices=ParkingSlot.VEHICLE_TYPE_CHOICES)

    from_dt = models.DateTimeField()
    to_dt = models.DateTimeField()
    # Actual entry/exit recorded by ParkingSession
    actual_entry_time = models.DateTimeField(null=True, blank=True)
    actual_exit_time = models.DateTimeField(null=True, blank=True)

    # Pre-calculated estimated amount; final amount in ParkingTransaction
    estimated_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    final_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Set on checkout; may differ from estimate if overstay",
    )
    currency = models.CharField(max_length=3, default="INR")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # QR code data (HMAC signed) stored as string; URL served via API
    qr_data = models.TextField(blank=True)
    qr_code_url = models.CharField(max_length=500, blank=True)

    # Customer contact snapshot (denormalised to avoid profile lookups)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.CharField(max_length=255, blank=True)

    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords(
        inherit=False,
        excluded_fields=["qr_data", "updated_at"],
        user_model=User,
    )

    class Meta:
        db_table = "parking_booking"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["slot", "status"]),
            models.Index(fields=["booking_reference"]),
        ]

    def __str__(self):
        return f"{self.booking_reference} — {self.customer}"

    @property
    def duration_minutes(self):
        start = self.actual_entry_time or self.from_dt
        end = self.actual_exit_time or self.to_dt
        delta = end - start
        return int(delta.total_seconds() / 60)

    @property
    def location(self):
        return self.slot.zone.location

    @property
    def location_name(self):
        return self.slot.zone.location.name

    @property
    def slot_code(self):
        return self.slot.slot_code


class ParkingSession(models.Model):
    """Records vehicle entry/exit at the physical location."""

    ENTRY_METHOD_APP = "app"
    ENTRY_METHOD_QR = "qr"
    ENTRY_METHOD_OTP = "otp"
    ENTRY_METHOD_FASTAG = "fastag"
    ENTRY_METHOD_ANPR = "anpr"
    ENTRY_METHOD_MANUAL = "manual"

    ENTRY_METHOD_CHOICES = [
        (ENTRY_METHOD_APP, "App"),
        (ENTRY_METHOD_QR, "QR Scan"),
        (ENTRY_METHOD_OTP, "OTP"),
        (ENTRY_METHOD_FASTAG, "FASTag"),
        (ENTRY_METHOD_ANPR, "ANPR"),
        (ENTRY_METHOD_MANUAL, "Manual"),
    ]

    booking = models.OneToOneField(
        ParkingBooking, on_delete=models.CASCADE, related_name="session"
    )
    vehicle_number = models.CharField(max_length=20, db_index=True)
    entry_time = models.DateTimeField(null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    entry_method = models.CharField(
        max_length=20, choices=ENTRY_METHOD_CHOICES, default=ENTRY_METHOD_QR
    )
    exit_method = models.CharField(
        max_length=20, choices=ENTRY_METHOD_CHOICES, null=True, blank=True
    )
    attendant = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="attended_parking_sessions",
    )
    entry_photo_url = models.CharField(max_length=500, blank=True)
    exit_photo_url = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parking_session"

    def __str__(self):
        return f"Session for {self.booking.booking_reference}"


# ─── Ticket & Transaction ────────────────────────────────────────────────────

class ParkingTicket(models.Model):
    """Digital parking ticket associated with a booking."""

    booking = models.OneToOneField(
        ParkingBooking, on_delete=models.CASCADE, related_name="ticket"
    )
    ticket_number = models.CharField(max_length=30, unique=True, db_index=True)
    pdf_url = models.CharField(max_length=500, blank=True)
    qr_image_url = models.CharField(max_length=500, blank=True)

    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    whatsapp_phone = models.CharField(max_length=20, blank=True)
    email_address = models.CharField(max_length=255, blank=True)

    print_count = models.PositiveSmallIntegerField(default=0)
    resend_count = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parking_ticket"

    def __str__(self):
        return f"Ticket #{self.ticket_number}"


class ParkingTransaction(models.Model):
    """Financial transaction tied to a parking booking."""

    METHOD_VOUCHER = "voucher"
    METHOD_FASTAG = "fastag"
    METHOD_PG = "pg"
    METHOD_CASH = "cash"

    METHOD_CHOICES = [
        (METHOD_VOUCHER, "Parkpe Voucher"),
        (METHOD_FASTAG, "FASTag"),
        (METHOD_PG, "Payment Gateway"),
        (METHOD_CASH, "Cash"),
    ]

    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    booking = models.ForeignKey(
        ParkingBooking, on_delete=models.PROTECT, related_name="transactions"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES)

    # Voucher reference (if paid via ParkPe voucher)
    voucher_transaction_id = models.IntegerField(
        null=True, blank=True,
        help_text="GiftVoucherTransaction PK from portal.models",
    )
    voucher_id = models.IntegerField(null=True, blank=True)

    gateway_reference = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    failure_reason = models.TextField(blank=True)

    transaction_type = models.CharField(
        max_length=20,
        choices=[("charge", "Charge"), ("refund", "Refund"), ("overstay", "Overstay Charge")],
        default="charge",
    )

    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parking_transaction"
        indexes = [
            models.Index(fields=["booking", "status"]),
            models.Index(fields=["idempotency_key"]),
        ]

    def __str__(self):
        return f"₹{self.amount} {self.payment_method} — {self.booking.booking_reference}"


# ─── Revenue & Operators ─────────────────────────────────────────────────────

class ParkingRevenue(models.Model):
    """Daily revenue rollup per location — for owner dashboard."""

    SETTLEMENT_PENDING = "pending"
    SETTLEMENT_PROCESSED = "processed"
    SETTLEMENT_PAID = "paid"

    location = models.ForeignKey(
        ParkingLocation, on_delete=models.CASCADE, related_name="revenue_records"
    )
    date = models.DateField(db_index=True)
    total_bookings = models.PositiveIntegerField(default=0)
    gross_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("5.00"),
        help_text="Parkpe commission percentage",
    )
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    net_owner_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    settlement_status = models.CharField(
        max_length=20,
        choices=[
            (SETTLEMENT_PENDING, "Pending"),
            (SETTLEMENT_PROCESSED, "Processed"),
            (SETTLEMENT_PAID, "Paid"),
        ],
        default=SETTLEMENT_PENDING,
    )
    settled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parking_revenue"
        unique_together = [("location", "date")]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.location.name} — {self.date} ₹{self.gross_revenue}"


class ParkingOperator(models.Model):
    """Links a Hub user to a parking location with an operator role."""

    ROLE_OWNER = "owner"
    ROLE_MANAGER = "manager"
    ROLE_ATTENDANT = "attendant"

    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_ATTENDANT, "Attendant"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="parking_operator_roles"
    )
    location = models.ForeignKey(
        ParkingLocation, on_delete=models.CASCADE, related_name="operators"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ATTENDANT)
    hub_assignment_id = models.IntegerField(
        null=True, blank=True,
        help_text="rbac.UserHubAssignment PK that granted this operator role",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parking_operator"
        unique_together = [("user", "location")]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["location", "role"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.role} @ {self.location.name}"
