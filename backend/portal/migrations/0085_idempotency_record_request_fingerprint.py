from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0084_parkpe_challan_record"),
    ]

    operations = [
        migrations.AddField(
            model_name="idempotencyrecord",
            name="request_fingerprint",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="SHA-256 fingerprint of normalized request payload for key reuse validation",
                max_length=64,
                null=True,
            ),
        ),
    ]
