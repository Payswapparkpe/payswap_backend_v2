from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0077_vehicle_fastag_biller_and_balance"),
    ]

    operations = [
        migrations.AddField(
            model_name="connectmessage",
            name="client_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="connectmessage",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connectmessage",
            name="delivery_status",
            field=models.CharField(
                choices=[("sent", "Sent"), ("delivered", "Delivered"), ("seen", "Seen"), ("failed", "Failed")],
                db_index=True,
                default="sent",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="connectmessage",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="connectmessage",
            name="seen_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="owner_archived",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="owner_last_read_message_id",
            field=models.PositiveBigIntegerField(db_index=True, default=0),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="owner_last_seen_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="owner_muted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="owner_pinned",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="scanner_archived",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="scanner_last_read_message_id",
            field=models.PositiveBigIntegerField(db_index=True, default=0),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="scanner_last_seen_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="scanner_muted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="scanner_pinned",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
