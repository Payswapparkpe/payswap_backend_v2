from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0085_idempotency_record_request_fingerprint"),
    ]

    operations = [
        migrations.AddField(
            model_name="kyc",
            name="document_file_keys",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="List of private S3 object keys for secure document access",
            ),
        ),
    ]
