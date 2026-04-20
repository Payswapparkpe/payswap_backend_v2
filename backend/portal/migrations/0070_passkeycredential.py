from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0069_connectmoderationaction"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasskeyCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("credential_id", models.CharField(db_index=True, max_length=512, unique=True)),
                ("public_key", models.BinaryField()),
                ("sign_count", models.BigIntegerField(default=0)),
                ("transports", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("label", models.CharField(blank=True, default="", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_used_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="passkey_credentials",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "portal_passkey_credential",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="passkeycredential",
            index=models.Index(fields=["user", "is_active"], name="portal_pass_user_id_1f7e72_idx"),
        ),
    ]
