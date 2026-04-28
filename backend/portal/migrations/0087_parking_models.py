"""
Migration: Add Parkpe Parking Platform models
ParkingLocation, ParkingZone, ParkingSlot, ParkingRate,
ParkingBooking, ParkingSession, ParkingTicket, ParkingTransaction,
ParkingRevenue, ParkingOperator
"""
import decimal
import uuid
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import simple_history.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0086_kyc_document_file_keys"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── ParkingLocation ─────────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingLocation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("address", models.TextField()),
                ("city", models.CharField(max_length=100)),
                ("state", models.CharField(max_length=100)),
                ("postal_code", models.CharField(max_length=10)),
                ("latitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("longitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("geofence_polygon", models.JSONField(blank=True, default=dict, help_text="GeoJSON polygon of the parking boundary for entry geo-validation")),
                ("hub_project_id", models.IntegerField(blank=True, help_text="rbac.Project PK — scopes operator assignments", null=True)),
                ("total_slots", models.PositiveIntegerField(default=0)),
                ("amenities", models.JSONField(blank=True, default=list, help_text='e.g. ["covered","cctv","ev_charging","valet","toilet"]')),
                ("opening_hours", models.JSONField(blank=True, default=dict, help_text='{"open":"06:00","close":"23:00","247":false}')),
                ("images", models.JSONField(blank=True, default=list)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(help_text="Hub user who owns this parking facility", on_delete=django.db.models.deletion.PROTECT, related_name="owned_parking_locations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "parking_location", "ordering": ["name"]},
        ),
        migrations.AddIndex(
            model_name="parkinglocation",
            index=models.Index(fields=["city", "is_active"], name="parking_loc_city_active_idx"),
        ),
        migrations.AddIndex(
            model_name="parkinglocation",
            index=models.Index(fields=["latitude", "longitude"], name="parking_loc_latlng_idx"),
        ),
        # HistoricalParkingLocation
        migrations.CreateModel(
            name="HistoricalParkingLocation",
            fields=[
                ("id", models.IntegerField(blank=True, db_index=True)),
                ("name", models.CharField(max_length=255)),
                ("address", models.TextField()),
                ("city", models.CharField(max_length=100)),
                ("state", models.CharField(max_length=100)),
                ("postal_code", models.CharField(max_length=10)),
                ("latitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("longitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("geofence_polygon", models.JSONField(blank=True, default=dict)),
                ("hub_project_id", models.IntegerField(blank=True, null=True)),
                ("total_slots", models.PositiveIntegerField(default=0)),
                ("amenities", models.JSONField(blank=True, default=list)),
                ("opening_hours", models.JSONField(blank=True, default=dict)),
                ("images", models.JSONField(blank=True, default=list)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(blank=True, editable=False)),
                ("updated_at", models.DateTimeField(blank=True, editable=False)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")], max_length=1)),
                ("history_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("owner", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "historical parking location", "verbose_name_plural": "historical parking locations", "ordering": ("-history_date", "-history_id"), "get_latest_by": ("history_date", "history_id")},
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),

        # ── ParkingZone ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingZone",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("zone_name", models.CharField(help_text='e.g. "Ground Floor", "Zone A"', max_length=100)),
                ("floor_level", models.IntegerField(default=0, help_text="0=Ground, 1=Floor1, -1=Basement1")),
                ("zone_type", models.CharField(choices=[("2W", "Two Wheeler"), ("4W", "Four Wheeler"), ("EV", "EV Charging"), ("VIP", "VIP"), ("HANDICAP", "Handicap"), ("HEAVY", "Heavy Vehicle")], default="4W", max_length=20)),
                ("total_slots", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="zones", to="portal.parkinglocation")),
            ],
            options={"db_table": "parking_zone", "ordering": ["floor_level", "display_order", "zone_name"]},
        ),
        migrations.AlterUniqueTogether(
            name="parkingzone",
            unique_together={("location", "zone_name")},
        ),

        # ── ParkingSlot ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingSlot",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slot_code", models.CharField(help_text='e.g. "A-101", "G-05"', max_length=20)),
                ("vehicle_type", models.CharField(choices=[("two_wheeler", "Two Wheeler"), ("four_wheeler", "Four Wheeler"), ("ev", "EV"), ("heavy_vehicle", "Heavy Vehicle")], default="four_wheeler", max_length=20)),
                ("status", models.CharField(choices=[("available", "Available"), ("occupied", "Occupied"), ("reserved", "Reserved"), ("blocked", "Blocked"), ("maintenance", "Maintenance")], default="available", max_length=20)),
                ("features", models.JSONField(blank=True, default=list, help_text='e.g. ["covered","ev_charging","cctv"]')),
                ("sensor_id", models.CharField(blank=True, help_text="IoT sensor / RFID tag for automated status updates", max_length=100, null=True, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("zone", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="slots", to="portal.parkingzone")),
            ],
            options={"db_table": "parking_slot"},
        ),
        migrations.AlterUniqueTogether(
            name="parkingslot",
            unique_together={("zone", "slot_code")},
        ),
        migrations.AddIndex(
            model_name="parkingslot",
            index=models.Index(fields=["status"], name="parking_slot_status_idx"),
        ),
        migrations.AddIndex(
            model_name="parkingslot",
            index=models.Index(fields=["zone", "status"], name="parking_slot_zone_status_idx"),
        ),

        # ── ParkingRate ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingRate",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vehicle_type", models.CharField(choices=[("two_wheeler", "Two Wheeler"), ("four_wheeler", "Four Wheeler"), ("ev", "EV"), ("heavy_vehicle", "Heavy Vehicle")], max_length=20)),
                ("base_rate", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), help_text="Fixed charge on entry (base fee)", max_digits=10, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0"))])),
                ("per_hour_rate", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0"))])),
                ("grace_minutes", models.PositiveSmallIntegerField(default=15)),
                ("daily_cap", models.DecimalField(blank=True, decimal_places=2, help_text="Max charge per day; null = no cap", max_digits=10, null=True)),
                ("overnight_rate", models.DecimalField(blank=True, decimal_places=2, help_text="Fixed overnight charge (22:00-06:00); null = regular rate", max_digits=10, null=True)),
                ("weekend_multiplier", models.DecimalField(decimal_places=2, default=decimal.Decimal("1.0"), help_text="e.g. 1.5 = 50% extra on weekends", max_digits=4)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rates", to="portal.parkinglocation")),
            ],
            options={"db_table": "parking_rate"},
        ),
        migrations.AlterUniqueTogether(
            name="parkingrate",
            unique_together={("location", "vehicle_type")},
        ),

        # ── ParkingBooking ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingBooking",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("booking_reference", models.CharField(db_index=True, help_text="Human-readable booking ref e.g. PKP-20240428-0001", max_length=20, unique=True)),
                ("vehicle_number", models.CharField(max_length=20)),
                ("vehicle_type", models.CharField(choices=[("two_wheeler", "Two Wheeler"), ("four_wheeler", "Four Wheeler"), ("ev", "EV"), ("heavy_vehicle", "Heavy Vehicle")], max_length=20)),
                ("from_dt", models.DateTimeField()),
                ("to_dt", models.DateTimeField()),
                ("actual_entry_time", models.DateTimeField(blank=True, null=True)),
                ("actual_exit_time", models.DateTimeField(blank=True, null=True)),
                ("estimated_amount", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=10)),
                ("final_amount", models.DecimalField(blank=True, decimal_places=2, help_text="Set on checkout; may differ from estimate if overstay", max_digits=10, null=True)),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("active", "Active"), ("completed", "Completed"), ("cancelled", "Cancelled"), ("expired", "Expired")], default="pending", max_length=20)),
                ("qr_data", models.TextField(blank=True)),
                ("qr_code_url", models.CharField(blank=True, max_length=500)),
                ("customer_name", models.CharField(blank=True, max_length=200)),
                ("customer_phone", models.CharField(blank=True, max_length=20)),
                ("customer_email", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("cancellation_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="parking_bookings", to=settings.AUTH_USER_MODEL)),
                ("slot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to="portal.parkingslot")),
            ],
            options={"db_table": "parking_booking", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="parkingbooking",
            index=models.Index(fields=["customer", "status"], name="parking_bkg_cust_status_idx"),
        ),
        migrations.AddIndex(
            model_name="parkingbooking",
            index=models.Index(fields=["slot", "status"], name="parking_bkg_slot_status_idx"),
        ),
        migrations.AddIndex(
            model_name="parkingbooking",
            index=models.Index(fields=["booking_reference"], name="parking_bkg_ref_idx"),
        ),
        # HistoricalParkingBooking
        migrations.CreateModel(
            name="HistoricalParkingBooking",
            fields=[
                ("id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)),
                ("booking_reference", models.CharField(db_index=True, max_length=20)),
                ("vehicle_number", models.CharField(max_length=20)),
                ("vehicle_type", models.CharField(max_length=20)),
                ("from_dt", models.DateTimeField()),
                ("to_dt", models.DateTimeField()),
                ("actual_entry_time", models.DateTimeField(blank=True, null=True)),
                ("actual_exit_time", models.DateTimeField(blank=True, null=True)),
                ("estimated_amount", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=10)),
                ("final_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("status", models.CharField(max_length=20)),
                ("qr_code_url", models.CharField(blank=True, max_length=500)),
                ("customer_name", models.CharField(blank=True, max_length=200)),
                ("customer_phone", models.CharField(blank=True, max_length=20)),
                ("customer_email", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("cancellation_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(blank=True, editable=False)),
                ("updated_at", models.DateTimeField(blank=True, editable=False)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")], max_length=1)),
                ("history_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("customer", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("slot", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to="portal.parkingslot")),
            ],
            options={"verbose_name": "historical parking booking", "ordering": ("-history_date", "-history_id"), "get_latest_by": ("history_date", "history_id")},
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),

        # ── ParkingSession ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingSession",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vehicle_number", models.CharField(db_index=True, max_length=20)),
                ("entry_time", models.DateTimeField(blank=True, null=True)),
                ("exit_time", models.DateTimeField(blank=True, null=True)),
                ("entry_method", models.CharField(choices=[("app", "App"), ("qr", "QR Scan"), ("otp", "OTP"), ("fastag", "FASTag"), ("anpr", "ANPR"), ("manual", "Manual")], default="qr", max_length=20)),
                ("exit_method", models.CharField(blank=True, choices=[("app", "App"), ("qr", "QR Scan"), ("otp", "OTP"), ("fastag", "FASTag"), ("anpr", "ANPR"), ("manual", "Manual")], max_length=20, null=True)),
                ("entry_photo_url", models.CharField(blank=True, max_length=500)),
                ("exit_photo_url", models.CharField(blank=True, max_length=500)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="session", to="portal.parkingbooking")),
                ("attendant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attended_parking_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "parking_session"},
        ),

        # ── ParkingTicket ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingTicket",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ticket_number", models.CharField(db_index=True, max_length=30, unique=True)),
                ("pdf_url", models.CharField(blank=True, max_length=500)),
                ("qr_image_url", models.CharField(blank=True, max_length=500)),
                ("whatsapp_sent_at", models.DateTimeField(blank=True, null=True)),
                ("email_sent_at", models.DateTimeField(blank=True, null=True)),
                ("whatsapp_phone", models.CharField(blank=True, max_length=20)),
                ("email_address", models.CharField(blank=True, max_length=255)),
                ("print_count", models.PositiveSmallIntegerField(default=0)),
                ("resend_count", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="ticket", to="portal.parkingbooking")),
            ],
            options={"db_table": "parking_ticket"},
        ),

        # ── ParkingTransaction ───────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingTransaction",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("payment_method", models.CharField(choices=[("voucher", "Parkpe Voucher"), ("fastag", "FASTag"), ("pg", "Payment Gateway"), ("cash", "Cash")], max_length=20)),
                ("voucher_transaction_id", models.IntegerField(blank=True, help_text="GiftVoucherTransaction PK from portal.models", null=True)),
                ("voucher_id", models.IntegerField(blank=True, null=True)),
                ("gateway_reference", models.CharField(blank=True, max_length=255)),
                ("idempotency_key", models.CharField(blank=True, db_index=True, max_length=255)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed"), ("refunded", "Refunded")], default="pending", max_length=20)),
                ("failure_reason", models.TextField(blank=True)),
                ("transaction_type", models.CharField(choices=[("charge", "Charge"), ("refund", "Refund"), ("overstay", "Overstay Charge")], default="charge", max_length=20)),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="portal.parkingbooking")),
            ],
            options={"db_table": "parking_transaction"},
        ),
        migrations.AddIndex(
            model_name="parkingtransaction",
            index=models.Index(fields=["booking", "status"], name="parking_txn_bkg_status_idx"),
        ),
        migrations.AddIndex(
            model_name="parkingtransaction",
            index=models.Index(fields=["idempotency_key"], name="parking_txn_idem_idx"),
        ),

        # ── ParkingRevenue ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingRevenue",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("total_bookings", models.PositiveIntegerField(default=0)),
                ("gross_revenue", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=12)),
                ("commission_pct", models.DecimalField(decimal_places=2, default=decimal.Decimal("5.00"), help_text="Parkpe commission percentage", max_digits=5)),
                ("commission_amount", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=12)),
                ("net_owner_amount", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=12)),
                ("settlement_status", models.CharField(choices=[("pending", "Pending"), ("processed", "Processed"), ("paid", "Paid")], default="pending", max_length=20)),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revenue_records", to="portal.parkinglocation")),
            ],
            options={"db_table": "parking_revenue", "ordering": ["-date"]},
        ),
        migrations.AlterUniqueTogether(
            name="parkingrevenue",
            unique_together={("location", "date")},
        ),

        # ── ParkingOperator ──────────────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingOperator",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("owner", "Owner"), ("manager", "Manager"), ("attendant", "Attendant")], default="attendant", max_length=20)),
                ("hub_assignment_id", models.IntegerField(blank=True, help_text="rbac.UserHubAssignment PK that granted this operator role", null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="parking_operator_roles", to=settings.AUTH_USER_MODEL)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="operators", to="portal.parkinglocation")),
            ],
            options={"db_table": "parking_operator"},
        ),
        migrations.AlterUniqueTogether(
            name="parkingoperator",
            unique_together={("user", "location")},
        ),
        migrations.AddIndex(
            model_name="parkingoperator",
            index=models.Index(fields=["user", "is_active"], name="parking_op_user_active_idx"),
        ),
        migrations.AddIndex(
            model_name="parkingoperator",
            index=models.Index(fields=["location", "role"], name="parking_op_loc_role_idx"),
        ),
    ]
