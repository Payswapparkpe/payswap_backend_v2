# Generic approval workflow (4-eye) for high-risk admin actions

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0024_strong_idempotency_and_partner_charge_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprovalRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("partner_wallet_credit", "Partner Wallet Credit"),
                            ("partner_wallet_debit", "Partner Wallet Debit"),
                            ("settlement_execute", "Settlement Execute / Mark Paid"),
                            ("refund_execute", "Refund Execution"),
                            ("voucher_status_override", "Voucher Status Override (Block/Cancel)"),
                            ("manual_balance_adjustment", "Manual Wallet/Voucher Balance Adjustment"),
                        ],
                        db_index=True,
                        help_text="High-risk action that requires approval",
                        max_length=64,
                    ),
                ),
                (
                    "entity_type",
                    models.CharField(
                        choices=[
                            ("wallet", "Wallet"),
                            ("settlement", "Settlement"),
                            ("voucher", "Voucher"),
                            ("payment", "Payment"),
                        ],
                        db_index=True,
                        help_text="Type of entity (wallet, settlement, voucher, payment)",
                        max_length=32,
                    ),
                ),
                (
                    "entity_id",
                    models.CharField(db_index=True, help_text="ID of the entity (e.g. partner id, settlement id, voucher id)", max_length=64),
                ),
                (
                    "payload",
                    models.JSONField(
                        default=dict,
                        help_text="Minimal data to execute (amount, reference_id, reason, etc.). Do not store secrets.",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("APPROVED", "Approved"),
                            ("REJECTED", "Rejected"),
                            ("EXPIRED", "Expired"),
                        ],
                        db_index=True,
                        default="PENDING",
                        help_text="PENDING=awaiting approval, APPROVED=executed, REJECTED=denied, EXPIRED=timed out",
                        max_length=20,
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, help_text="When the request was approved or rejected (UTC)", null=True)),
                (
                    "requested_at",
                    models.DateTimeField(auto_now_add=True, db_index=True, help_text="When the request was created (UTC)"),
                ),
                (
                    "rejection_reason",
                    models.TextField(blank=True, help_text="Reason for rejection if status=REJECTED", null=True),
                ),
                (
                    "execution_result",
                    models.JSONField(blank=True, default=dict, help_text="Result of execution (transaction_id, etc.) for audit"),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        help_text="User who requested the action (maker)",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approval_requests_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who approved or rejected (checker)",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approval_requests_approved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Approval Request",
                "verbose_name_plural": "Approval Requests",
                "db_table": "portal_approval_request",
                "ordering": ["-requested_at"],
            },
        ),
    ]
