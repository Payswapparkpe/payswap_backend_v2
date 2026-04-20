from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0064_notificationbanner"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationCampaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(db_index=True, max_length=140)),
                ("campaign_type", models.CharField(choices=[("manual", "Manual"), ("event", "Event")], db_index=True, default="manual", max_length=16)),
                ("event_key", models.CharField(blank=True, db_index=True, default="", max_length=80)),
                ("description", models.CharField(blank=True, default="", max_length=320)),
                ("channels", models.JSONField(blank=True, default=list)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("quiet_hours_start", models.TimeField(blank=True, null=True)),
                ("quiet_hours_end", models.TimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("scheduled", "Scheduled"), ("running", "Running"), ("paused", "Paused"), ("completed", "Completed")], db_index=True, default="draft", max_length=16)),
                ("starts_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notification_campaigns_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "portal_notification_campaign",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["campaign_type", "status"], name="portal_notif_campaign__998749_idx"),
                    models.Index(fields=["event_key", "status"], name="portal_notif_event_k_dfbec3_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="DevicePushToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(max_length=512, unique=True)),
                ("device_platform", models.CharField(choices=[("ios", "iOS"), ("android", "Android"), ("web", "Web")], db_index=True, default="android", max_length=16)),
                ("app_platform", models.CharField(choices=[("both", "Both"), ("parkpe", "ParkPe"), ("payswap", "Payswap")], db_index=True, default="parkpe", max_length=16)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("last_seen_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="device_push_tokens", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "portal_device_push_token",
                "ordering": ["-updated_at"],
                "indexes": [
                    models.Index(fields=["user", "is_active"], name="portal_devi_user_id_8c84f1_idx"),
                    models.Index(fields=["app_platform", "device_platform"], name="portal_devi_app_pla_2714b5_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="NotificationAudienceRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(choices=[("both", "Both"), ("parkpe", "ParkPe"), ("payswap", "Payswap")], db_index=True, default="both", max_length=16)),
                ("service_code", models.CharField(blank=True, db_index=True, default="", max_length=48)),
                ("screen_code", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("role_code", models.CharField(blank=True, db_index=True, default="", max_length=40)),
                ("user_ids", models.JSONField(blank=True, default=list)),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audience_rules", to="portal.notificationcampaign")),
            ],
            options={
                "db_table": "portal_notification_audience_rule",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["platform", "service_code", "screen_code"], name="portal_notif_platform_688f13_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="NotificationDeliveryLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("in_app", "In-App"), ("push", "Push"), ("sms", "SMS"), ("email", "Email"), ("banner", "Banner")], db_index=True, max_length=16)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("sent", "Sent"), ("delivered", "Delivered"), ("failed", "Failed"), ("read", "Read")], db_index=True, default="queued", max_length=16)),
                ("destination", models.CharField(blank=True, default="", max_length=255)),
                ("provider", models.CharField(blank=True, default="", max_length=64)),
                ("provider_message_id", models.CharField(blank=True, db_index=True, default="", max_length=255)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("response_payload", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campaign", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_logs", to="portal.notificationcampaign")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notification_delivery_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "portal_notification_delivery_log",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["channel", "status", "-created_at"], name="portal_notif_channel_18d9d9_idx"),
                    models.Index(fields=["campaign", "status"], name="portal_notif_campaign_f4bfaa_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="NotificationMessageTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("in_app", "In-App"), ("push", "Push"), ("sms", "SMS"), ("email", "Email"), ("banner", "Banner")], db_index=True, max_length=16)),
                ("subject", models.CharField(blank=True, default="", max_length=160)),
                ("title", models.CharField(blank=True, default="", max_length=160)),
                ("body", models.TextField(blank=True, default="")),
                ("cta_text", models.CharField(blank=True, default="", max_length=64)),
                ("cta_url", models.CharField(blank=True, default="", max_length=255)),
                ("image_url", models.CharField(blank=True, default="", max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="templates", to="portal.notificationcampaign")),
            ],
            options={
                "db_table": "portal_notification_message_template",
                "ordering": ["channel", "-created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("campaign", "channel"), name="portal_notification_template_campaign_channel_unique"),
                ],
            },
        ),
        migrations.CreateModel(
            name="UserNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("in_app", "In-App"), ("push", "Push"), ("sms", "SMS"), ("email", "Email"), ("banner", "Banner")], db_index=True, default="in_app", max_length=16)),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField()),
                ("deep_link", models.CharField(blank=True, default="", max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("campaign", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="user_notifications", to="portal.notificationcampaign")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "portal_user_notification",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "is_read", "-created_at"], name="portal_user_user_id_4cb00e_idx"),
                ],
            },
        ),
    ]
