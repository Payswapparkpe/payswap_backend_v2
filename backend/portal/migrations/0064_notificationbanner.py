from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0063_alter_logentry_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationBanner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(db_index=True, max_length=120)),
                ("title", models.CharField(max_length=120)),
                ("message", models.CharField(max_length=320)),
                ("cta_text", models.CharField(blank=True, default="", max_length=48)),
                ("cta_url", models.CharField(blank=True, default="", max_length=255)),
                ("image_url", models.CharField(blank=True, default="", max_length=255)),
                ("bg_color", models.CharField(blank=True, default="#1f4f94", max_length=16)),
                ("text_color", models.CharField(blank=True, default="#ffffff", max_length=16)),
                ("platform", models.CharField(choices=[("both", "Both"), ("parkpe", "ParkPe"), ("payswap", "Payswap")], db_index=True, default="both", max_length=16)),
                ("slot", models.CharField(choices=[("bbps_right_rail", "BBPS Right Rail"), ("dashboard_top", "Dashboard Top"), ("service_inline", "Service Inline")], db_index=True, default="bbps_right_rail", max_length=32)),
                ("service_code", models.CharField(blank=True, db_index=True, default="", max_length=48)),
                ("screen_code", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("priority", models.IntegerField(db_index=True, default=100)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("starts_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notification_banners_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "portal_notification_banner",
                "ordering": ["priority", "-created_at"],
                "indexes": [
                    models.Index(fields=["platform", "slot", "is_active"], name="portal_notif_platform_fcf2f6_idx"),
                    models.Index(fields=["service_code", "screen_code"], name="portal_notif_service_81e486_idx"),
                ],
            },
        ),
    ]
