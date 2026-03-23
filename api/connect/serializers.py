"""
ParkPe Connect API – serializers for Vehicle and public scan response.
"""
from rest_framework import serializers
from portal.models import Vehicle, VehicleQRCode

from .rc_visibility import get_vehicle_rc_display


class VehicleSerializer(serializers.ModelSerializer):
    """Owner-facing vehicle CRUD; includes vehicle_rc when RC data is fetched and not locked."""
    qr_code = serializers.SerializerMethodField(read_only=True)
    vehicle_rc = serializers.SerializerMethodField(read_only=True)
    rc_locked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id',
            'vehicle_type',
            'registration_number',
            'brand',
            'model',
            'year',
            'photo',
            'is_primary',
            'qr_code',
            'vehicle_rc',
            'rc_locked',
            'rc_view_paid_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_qr_code(self, obj):
        qr = getattr(obj, 'qr_code', None)
        if qr:
            return qr.code
        return None

    def _get_rc_visibility(self, obj):
        request = self.context.get("request")
        if request and getattr(request, "user", None):
            return get_vehicle_rc_display(obj, request.user)
        rc = getattr(obj, "rc_data", None)
        if rc and getattr(rc, "raw_response", None):
            return None, True  # no user context: treat as locked
        return None, False

    def get_vehicle_rc(self, obj):
        raw, _ = self._get_rc_visibility(obj)
        return raw

    def get_rc_locked(self, obj):
        _, rc_locked = self._get_rc_visibility(obj)
        return rc_locked


class VehicleCreateSerializer(serializers.ModelSerializer):
    """Create vehicle; qr_code created server-side."""

    class Meta:
        model = Vehicle
        fields = [
            'vehicle_type',
            'registration_number',
            'brand',
            'model',
            'year',
            'photo',
            'is_primary',
        ]


class VehicleByQRResponseSerializer(serializers.Serializer):
    """Public scan response – masked vehicle and owner, no PII."""
    vehicle_id = serializers.IntegerField()
    qr_code = serializers.CharField()
    registration_number_masked = serializers.CharField()
    brand = serializers.CharField(allow_blank=True)
    model = serializers.CharField(allow_blank=True)
    year = serializers.IntegerField(allow_null=True)
    owner_display_name = serializers.CharField()
    owner_phone_configured = serializers.BooleanField(
        help_text='True if owner has a phone number registered; frontend can disable Call if False',
    )
    contact_options = serializers.ListField(
        child=serializers.CharField(),
        help_text='Available options: call, chat',
    )
