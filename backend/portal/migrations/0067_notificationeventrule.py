from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0066_notificationbanner_campaign"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationEventRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.CharField(db_index=True, max_length=80)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("priority", models.IntegerField(db_index=True, default=100)),
                ("condition_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_rules", to="portal.notificationcampaign")),
            ],
            options={
                "db_table": "portal_notification_event_rule",
                "ordering": ["priority", "-created_at"],
                "indexes": [
                    models.Index(fields=["event_key", "is_active"], name="portal_notif_event_k_00d938_idx"),
                ],
            },
        ),
    ]
