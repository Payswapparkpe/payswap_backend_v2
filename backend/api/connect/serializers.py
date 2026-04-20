"""
ParkPe Connect API – serializers for Vehicle and public scan response.
"""
from django.db.models import Q
from rest_framework import serializers
from portal.models import BBPSOperator, Vehicle, VehicleQRCode

from .rc_visibility import get_vehicle_rc_display


class VehicleSerializer(serializers.ModelSerializer):
    """Owner-facing vehicle CRUD; includes vehicle_rc when RC data is fetched and not locked."""
    qr_code = serializers.SerializerMethodField(read_only=True)
    vehicle_rc = serializers.SerializerMethodField(read_only=True)
    rc_locked = serializers.SerializerMethodField(read_only=True)
    rc_payment_required_before_fetch = serializers.SerializerMethodField(read_only=True)
    fastag_balance = serializers.SerializerMethodField(read_only=True)

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
            'fastag_biller_id',
            'fastag_balance',
            'fastag_balance_fetched_at',
            'qr_code',
            'vehicle_rc',
            'rc_locked',
            'rc_payment_required_before_fetch',
            'rc_view_paid_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'fastag_balance', 'fastag_balance_fetched_at']

    def get_fastag_balance(self, obj):
        v = getattr(obj, "fastag_balance_last_value", None)
        if v is None:
            return None
        return float(v)

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

    def _cached_first_consumer_vehicle_pk(self):
        """Oldest consumer Connect vehicle for this user (same rule as fetch-rc paywall)."""
        if "_first_consumer_vehicle_pk" not in self.context:
            request = self.context.get("request")
            user = getattr(request, "user", None) if request else None
            if user and getattr(user, "is_authenticated", False):
                pk = (
                    Vehicle.objects.filter(user=user, connect_scope=Vehicle.SCOPE_CONSUMER)
                    .order_by("created_at")
                    .values_list("pk", flat=True)
                    .first()
                )
            else:
                pk = None
            self.context["_first_consumer_vehicle_pk"] = pk
        return self.context["_first_consumer_vehicle_pk"]

    def get_rc_payment_required_before_fetch(self, obj):
        """True when RC is not stored yet but fetch-rc requires ₹50 voucher payment (2nd+ vehicles)."""
        if getattr(obj, "rc_view_paid_at", None):
            return False
        rc = getattr(obj, "rc_data", None)
        if rc and getattr(rc, "raw_response", None):
            return False
        first_pk = self._cached_first_consumer_vehicle_pk()
        return first_pk is not None and obj.pk != first_pk

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
            'fastag_biller_id',
        ]

    def validate_fastag_biller_id(self, value):
        v = (value or "").strip()
        if not v:
            return ""
        rec = (
            BBPSOperator.objects.filter(is_active=True)
            .filter(Q(biller_id=v) | Q(op=v))
            .only("biller_id", "op")
            .first()
        )
        if not rec:
            raise serializers.ValidationError("Unknown or inactive FASTag biller. Pick an issuer from the list.")
        canonical = (rec.biller_id or rec.op or v).strip()
        return canonical

    def update(self, instance, validated_data):
        old_biller = (instance.fastag_biller_id or "").strip()
        new_biller = (validated_data.get("fastag_biller_id", old_biller) if "fastag_biller_id" in validated_data else old_biller)
        new_biller = (new_biller or "").strip()
        if "fastag_biller_id" in validated_data:
            if not new_biller or new_biller != old_biller:
                instance.fastag_balance_last_value = None
                instance.fastag_balance_fetched_at = None
        return super().update(instance, validated_data)


class VehicleByQRResponseSerializer(serializers.Serializer):
    """Public scan response – vehicle registration (normalized full number) and owner label; phones not exposed."""
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
