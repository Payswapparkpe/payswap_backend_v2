from django.contrib import admin
from .models import ServiceCategory, APIRegistry, APILog, APIDowntimeEvent


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["code", "name"]


@admin.register(APIRegistry)
class APIRegistryAdmin(admin.ModelAdmin):
    list_display = [
        "api_name",
        "endpoint",
        "http_method",
        "version",
        "status",
        "service_category",
        "module_name",
        "updated_at",
    ]
    list_filter = ["version", "status", "http_method", "service_category"]
    search_fields = ["api_name", "endpoint", "module_name"]
    raw_id_fields = ["created_by", "updated_by"]


@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    list_display = [
        "request_id",
        "api_registry",
        "principal_type",
        "status_code",
        "duration_ms",
        "created_at",
    ]
    list_filter = ["principal_type", "status_code", "created_at"]
    search_fields = ["request_id", "response_id"]
    raw_id_fields = ["user", "api_key"]
    readonly_fields = [
        "api_registry",
        "request_id",
        "response_id",
        "principal_type",
        "user",
        "api_key",
        "status_code",
        "duration_ms",
        "error_type",
        "error_message",
        "client_ip",
        "user_agent",
        "request_meta",
        "response_meta",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False


@admin.register(APIDowntimeEvent)
class APIDowntimeEventAdmin(admin.ModelAdmin):
    list_display = ["api_registry", "started_at", "ended_at", "reason", "created_at"]
    list_filter = ["started_at"]
    raw_id_fields = ["api_registry"]
