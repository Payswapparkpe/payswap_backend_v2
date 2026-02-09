"""
API Management models - Centralized API Registry, Control & Monitoring.
"""
from django.conf import settings
from django.db import models


class ServiceCategory(models.Model):
    """Service category (BBPS, Wallet, Parking, Fastag, Auth, etc.)."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_management_service_category"
        verbose_name = "Service Category"
        verbose_name_plural = "Service Categories"
        ordering = ["code"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class APIProduct(models.Model):
    """
    Product-level API switch per platform (Parkpe / Payswap).
    One toggle per product (e.g. Mobikwik BBPS) – when OFF, all APIs under that product are disabled for that platform.
    """
    PLATFORM_PARKPE = "parkpe"
    PLATFORM_PAYSWAP = "payswap"
    PLATFORM_CHOICES = [
        (PLATFORM_PARKPE, "Parkpe"),
        (PLATFORM_PAYSWAP, "Payswap"),
    ]

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, db_index=True)
    product_slug = models.CharField(
        max_length=80,
        db_index=True,
        help_text="e.g. mobikwik_bbps, euronet_bbps – used in code to check if product is enabled",
    )
    name = models.CharField(max_length=150, help_text="Display name e.g. Mobikwik BBPS")
    enabled = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0, help_text="Order in admin UI")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_management_api_product"
        verbose_name = "API Product"
        verbose_name_plural = "API Products"
        ordering = ["platform", "display_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "product_slug"],
                name="api_management_product_platform_slug_unique",
            )
        ]
        indexes = [
            models.Index(fields=["platform", "enabled"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.platform})"


class APIRegistry(models.Model):
    """Central registry for every managed API endpoint."""

    STATUS_ON = "ON"
    STATUS_OFF = "OFF"
    STATUS_CHOICES = [
        (STATUS_ON, "ON"),
        (STATUS_OFF, "OFF"),
    ]

    HTTP_METHODS = [
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("PATCH", "PATCH"),
        ("DELETE", "DELETE"),
        ("HEAD", "HEAD"),
        ("OPTIONS", "OPTIONS"),
    ]

    VERSION_CHOICES = [
        ("v1", "v1"),
        ("v2", "v2"),
    ]

    service_category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.PROTECT,
        related_name="apis",
        null=True,
        blank=True,
        help_text="Service category (BBPS, Wallet, etc.)",
    )
    module_name = models.CharField(max_length=100, db_index=True, help_text="Logical module name")
    api_name = models.CharField(max_length=150, help_text="Human-readable API name")
    endpoint = models.CharField(max_length=500, help_text="Path template e.g. /api/v1/bbps/billers/")
    http_method = models.CharField(max_length=10, choices=HTTP_METHODS, db_index=True)
    version = models.CharField(max_length=10, choices=VERSION_CHOICES, db_index=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_OFF, db_index=True
    )
    # Access: min_role_hierarchy (int) or allowed_role_codes (JSON list)
    min_role_hierarchy = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minimum portal.Role.hierarchy_level (null = no hierarchy check)",
    )
    allowed_role_codes = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed role codes e.g. ['admin','user','retailer']. Empty = use min_role_hierarchy only.",
    )
    required_permissions = models.JSONField(
        default=list,
        blank=True,
        help_text="Django permission codenames e.g. ['portal.view_user']",
    )
    frontend_mapping = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"app": "parkpe", "featureModule": "bbps", "actionKey": "listBillers"}',
    )
    rate_limit = models.JSONField(
        default=dict,
        blank=True,
        help_text='e.g. {"scope": "user", "rate": "60/min"} or {"scope": "ip", "rate": "100/hour"}',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "api_management_api_registry"
        verbose_name = "API Registry"
        verbose_name_plural = "API Registries"
        ordering = ["version", "module_name", "api_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "http_method", "endpoint"],
                name="api_management_registry_version_method_endpoint_unique",
            )
        ]
        indexes = [
            models.Index(fields=["version", "status"]),
            models.Index(fields=["service_category", "status"]),
        ]

    def __str__(self):
        return f"{self.http_method} {self.endpoint} ({self.version})"


class APILog(models.Model):
    """Request/response log for managed APIs."""

    PRINCIPAL_USER = "user"
    PRINCIPAL_API_KEY = "api_key"
    PRINCIPAL_ANON = "anon"
    PRINCIPAL_CHOICES = [
        (PRINCIPAL_USER, "User"),
        (PRINCIPAL_API_KEY, "API Key"),
        (PRINCIPAL_ANON, "Anonymous"),
    ]

    api_registry = models.ForeignKey(
        APIRegistry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    response_id = models.CharField(max_length=100, blank=True, null=True)
    principal_type = models.CharField(
        max_length=20, choices=PRINCIPAL_CHOICES, default=PRINCIPAL_ANON, db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_management_logs",
    )
    api_key = models.ForeignKey(
        "portal.APIKey",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_management_logs",
    )
    status_code = models.IntegerField(null=True, blank=True, db_index=True)
    duration_ms = models.FloatField(null=True, blank=True)
    error_type = models.CharField(max_length=200, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(blank=True, null=True)
    request_meta = models.JSONField(default=dict, blank=True, help_text="Sanitized request metadata")
    response_meta = models.JSONField(default=dict, blank=True, help_text="Sanitized response metadata")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "api_management_api_log"
        verbose_name = "API Log"
        verbose_name_plural = "API Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["api_registry", "-created_at"]),
            models.Index(fields=["status_code", "-created_at"]),
            models.Index(fields=["principal_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.request_id or 'n/a'} {self.status_code} @ {self.created_at}"


class APIDowntimeEvent(models.Model):
    """Computed or manual downtime window per API (for monitoring)."""

    api_registry = models.ForeignKey(
        APIRegistry,
        on_delete=models.CASCADE,
        related_name="downtime_events",
    )
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reason = models.CharField(max_length=255, blank=True, null=True)
    threshold_trigger = models.JSONField(
        default=dict,
        blank=True,
        help_text="e.g. failure_rate_pct, latency_p99_ms",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_management_api_downtime_event"
        verbose_name = "API Downtime Event"
        verbose_name_plural = "API Downtime Events"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["api_registry", "-started_at"]),
        ]

    def __str__(self):
        return f"{self.api_registry_id} {self.started_at} - {self.ended_at or 'ongoing'}"
