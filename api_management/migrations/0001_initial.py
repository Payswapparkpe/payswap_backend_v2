# Generated manually for api_management app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portal", "0025_add_approval_request"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceCategory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(db_index=True, max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("inactive", "Inactive")],
                        db_index=True,
                        default="active",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Service Category",
                "verbose_name_plural": "Service Categories",
                "db_table": "api_management_service_category",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="APIRegistry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "module_name",
                    models.CharField(db_index=True, max_length=100),
                ),
                ("api_name", models.CharField(max_length=150)),
                ("endpoint", models.CharField(max_length=500)),
                (
                    "http_method",
                    models.CharField(
                        choices=[
                            ("GET", "GET"),
                            ("POST", "POST"),
                            ("PUT", "PUT"),
                            ("PATCH", "PATCH"),
                            ("DELETE", "DELETE"),
                            ("HEAD", "HEAD"),
                            ("OPTIONS", "OPTIONS"),
                        ],
                        db_index=True,
                        max_length=10,
                    ),
                ),
                (
                    "version",
                    models.CharField(
                        choices=[("v1", "v1"), ("v2", "v2")],
                        db_index=True,
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("ON", "ON"), ("OFF", "OFF")],
                        db_index=True,
                        default="OFF",
                        max_length=10,
                    ),
                ),
                ("min_role_hierarchy", models.IntegerField(blank=True, null=True)),
                (
                    "allowed_role_codes",
                    models.JSONField(
                        blank=True,
                        default=list,
                    ),
                ),
                (
                    "required_permissions",
                    models.JSONField(
                        blank=True,
                        default=list,
                    ),
                ),
                (
                    "frontend_mapping",
                    models.JSONField(
                        blank=True,
                        default=dict,
                    ),
                ),
                (
                    "rate_limit",
                    models.JSONField(
                        blank=True,
                        default=dict,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "service_category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="apis",
                        to="api_management.servicecategory",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "API Registry",
                "verbose_name_plural": "API Registries",
                "db_table": "api_management_api_registry",
                "ordering": ["version", "module_name", "api_name"],
            },
        ),
        migrations.AddConstraint(
            model_name="apiregistry",
            constraint=models.UniqueConstraint(
                fields=("version", "http_method", "endpoint"),
                name="api_management_registry_version_method_endpoint_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="apiregistry",
            index=models.Index(
                fields=["version", "status"],
                name="api_managem_version_8b0b0d_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="apiregistry",
            index=models.Index(
                fields=["service_category", "status"],
                name="api_managem_service_2c0e8a_idx",
            ),
        ),
        migrations.CreateModel(
            name="APIDowntimeEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("started_at", models.DateTimeField(db_index=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True, db_index=True)),
                ("reason", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "threshold_trigger",
                    models.JSONField(blank=True, default=dict),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "api_registry",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="downtime_events",
                        to="api_management.apiregistry",
                    ),
                ),
            ],
            options={
                "verbose_name": "API Downtime Event",
                "verbose_name_plural": "API Downtime Events",
                "db_table": "api_management_api_downtime_event",
                "ordering": ["-started_at"],
            },
        ),
        migrations.AddIndex(
            model_name="apidowntimeevent",
            index=models.Index(
                fields=["api_registry", "-started_at"],
                name="api_managem_api_reg_3a1f2b_idx",
            ),
        ),
        migrations.CreateModel(
            name="APILog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "request_id",
                    models.CharField(blank=True, db_index=True, max_length=100, null=True),
                ),
                (
                    "response_id",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "principal_type",
                    models.CharField(
                        choices=[
                            ("user", "User"),
                            ("api_key", "API Key"),
                            ("anon", "Anonymous"),
                        ],
                        db_index=True,
                        default="anon",
                        max_length=20,
                    ),
                ),
                ("status_code", models.IntegerField(blank=True, null=True, db_index=True)),
                ("duration_ms", models.FloatField(blank=True, null=True)),
                (
                    "error_type",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                ("error_message", models.TextField(blank=True, null=True)),
                (
                    "client_ip",
                    models.GenericIPAddressField(blank=True, null=True, db_index=True),
                ),
                ("user_agent", models.TextField(blank=True, null=True)),
                (
                    "request_meta",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "response_meta",
                    models.JSONField(blank=True, default=dict),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "api_key",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="api_management_logs",
                        to="portal.apikey",
                    ),
                ),
                (
                    "api_registry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="logs",
                        to="api_management.apiregistry",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="api_management_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "API Log",
                "verbose_name_plural": "API Logs",
                "db_table": "api_management_api_log",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="apilog",
            index=models.Index(
                fields=["api_registry", "-created_at"],
                name="api_managem_api_reg_1d4e5f_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="apilog",
            index=models.Index(
                fields=["status_code", "-created_at"],
                name="api_managem_status_7a2b3c_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="apilog",
            index=models.Index(
                fields=["principal_type", "-created_at"],
                name="api_managem_princip_9e8f0a_idx",
            ),
        ),
    ]
