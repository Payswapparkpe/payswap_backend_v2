from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0089_parking_exit_payment_and_tx_pin"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParkPeSavedVehicle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("registration_number", models.CharField(db_index=True, max_length=32)),
                ("nickname", models.CharField(blank=True, default="", max_length=64)),
                ("is_primary", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_known_pending_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="parkpe_saved_vehicles", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "ParkPe Saved Vehicle",
                "verbose_name_plural": "ParkPe Saved Vehicles",
                "db_table": "portal_parkpe_saved_vehicle",
                "ordering": ["-is_primary", "-updated_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="parkpesavedvehicle",
            constraint=models.UniqueConstraint(fields=("user", "registration_number"), name="uniq_parkpe_saved_vehicle_user_reg"),
        ),
        migrations.AddIndex(
            model_name="parkpesavedvehicle",
            index=models.Index(fields=["user", "-updated_at"], name="portal_park_user_id_7e3f7f_idx"),
        ),
        migrations.CreateModel(
            name="ParkPeChallanPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("challan_ref", models.CharField(db_index=True, default="", max_length=255)),
                ("challan_number", models.CharField(db_index=True, max_length=128)),
                ("vehicle_number", models.CharField(db_index=True, max_length=32)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("currency", models.CharField(default="INR", max_length=8)),
                ("payment_method", models.CharField(blank=True, default="", max_length=32)),
                ("transaction_id", models.CharField(db_index=True, default="", max_length=128)),
                ("receipt_number", models.CharField(db_index=True, default="", max_length=128)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")], db_index=True, default="pending", max_length=16)),
                ("vendor_status", models.CharField(blank=True, default="", max_length=255)),
                ("vendor_message", models.TextField(blank=True, default="")),
                ("request_json", models.JSONField(blank=True, null=True)),
                ("response_json", models.JSONField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("challan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payment_attempts", to="portal.parkpechallanrecord")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="parkpe_challan_payments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "ParkPe Challan Payment",
                "verbose_name_plural": "ParkPe Challan Payments",
                "db_table": "portal_parkpe_challan_payment",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="parkpechallanpayment",
            index=models.Index(fields=["user", "-created_at"], name="portal_park_user_id_2de136_idx"),
        ),
        migrations.AddIndex(
            model_name="parkpechallanpayment",
            index=models.Index(fields=["user", "status", "-updated_at"], name="portal_park_user_id_7347e1_idx"),
        ),
        migrations.AddIndex(
            model_name="parkpechallanpayment",
            index=models.Index(fields=["challan_number", "vehicle_number"], name="portal_park_challan_5e7c0d_idx"),
        ),
    ]
