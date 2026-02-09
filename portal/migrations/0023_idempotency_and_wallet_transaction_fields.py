# Generated migration: IdempotencyRecord model + WalletTransaction audit fields
# Financial safety: idempotency for money-moving APIs; wallet transaction audit trail

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0022_add_brand_api_identifier"),
    ]

    operations = [
        # WalletTransaction: add description, reference_id, metadata, performed_by for audit/idempotency
        migrations.AddField(
            model_name="wallettransaction",
            name="description",
            field=models.TextField(blank=True, null=True, help_text="Transaction description"),
        ),
        migrations.AddField(
            model_name="wallettransaction",
            name="reference_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="External reference ID for idempotency/audit",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="wallettransaction",
            name="metadata",
            field=models.JSONField(blank=True, default=dict, help_text="Additional transaction metadata"),
        ),
        migrations.AddField(
            model_name="wallettransaction",
            name="performed_by",
            field=models.ForeignKey(
                blank=True,
                help_text="User who performed the transaction",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="performed_wallet_transactions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # IdempotencyRecord for money-moving API idempotency (24h TTL)
        migrations.CreateModel(
            name="IdempotencyRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "scope",
                    models.CharField(db_index=True, help_text="Scope: e.g. partner_123:v2:voucher_issue", max_length=255),
                ),
                (
                    "idempotency_key",
                    models.CharField(
                        db_index=True,
                        help_text="Client-provided idempotency key (header or body)",
                        max_length=255,
                    ),
                ),
                (
                    "response_http_status",
                    models.IntegerField(help_text="Stored response HTTP status (200, 201, 400, etc.)"),
                ),
                (
                    "response_body",
                    models.TextField(help_text="Stored response body (JSON) to return on replay"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "verbose_name": "Idempotency Record",
                "verbose_name_plural": "Idempotency Records",
                "db_table": "portal_idempotency_record",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.UniqueConstraint(
                fields=("scope", "idempotency_key"),
                name="portal_idempotency_scope_key_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="idempotencyrecord",
            index=models.Index(fields=["scope", "idempotency_key"], name="portal_idemp_scope_key_idx"),
        ),
        migrations.AddIndex(
            model_name="idempotencyrecord",
            index=models.Index(fields=["created_at"], name="portal_idemp_created_idx"),
        ),
    ]
