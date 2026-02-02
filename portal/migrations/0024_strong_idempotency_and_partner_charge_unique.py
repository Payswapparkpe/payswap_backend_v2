# Strong idempotency (execute-once) + partner charge double-debit prevention
# - IdempotencyRecord: status PENDING|COMPLETED|FAILED; response fields nullable when PENDING
# - ResellerPartnerTransaction: unique (partner, reference_id) for REVENUE when reference_id set

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0023_idempotency_and_wallet_transaction_fields"),
    ]

    operations = [
        # IdempotencyRecord: add status for strong idempotency (reserve at start, complete/fail after)
        migrations.AddField(
            model_name="idempotencyrecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("COMPLETED", "Completed"),
                    ("FAILED", "Failed"),
                ],
                db_index=True,
                default="COMPLETED",  # existing rows were stored after execution
                help_text="PENDING=reserved, COMPLETED=stored response, FAILED=error",
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="idempotencyrecord",
            name="response_http_status",
            field=models.IntegerField(
                blank=True,
                help_text="Stored response HTTP status (set when status=COMPLETED)",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="idempotencyrecord",
            name="response_body",
            field=models.TextField(
                blank=True,
                help_text="Stored response body (JSON) to return on replay when COMPLETED",
                null=True,
            ),
        ),
        # ResellerPartnerTransaction: at most one REVENUE per (partner, reference_id) when reference_id set
        migrations.AddConstraint(
            model_name="resellerpartnertransaction",
            constraint=models.UniqueConstraint(
                condition=models.Q(transaction_type="REVENUE")
                & models.Q(reference_id__isnull=False)
                & ~models.Q(reference_id=""),
                fields=("partner", "reference_id"),
                name="partner_revenue_reference_id_unique",
            ),
        ),
    ]
