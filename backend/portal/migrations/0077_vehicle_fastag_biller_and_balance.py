# Generated manually for Connect FASTag balance (BBPS per-vehicle)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0076_tax_service_profile_and_billing_document"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="fastag_biller_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="BBPS FASTag biller id (from Mobikwik/BBPSOperator); user-selected issuer",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="fastag_balance_last_value",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Last FASTag balance from BBPS View Bill (fetch_bill)",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="fastag_balance_fetched_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When fastag_balance_last_value was last refreshed",
                null=True,
            ),
        ),
    ]
