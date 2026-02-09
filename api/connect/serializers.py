"""
ParkPe Connect API – serializers for Vehicle and public scan response.
"""
from rest_framework import serializers
from portal.models import Vehicle, VehicleQRCode


class VehicleSerializer(serializers.ModelSerializer):
    """Owner-facing vehicle CRUD."""
    qr_code = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id',
            'registration_number',
            'brand',
            'model',
            'year',
            'photo',
            'is_primary',
            'qr_code',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_qr_code(self, obj):
        qr = getattr(obj, 'qr_code', None)
        if qr:
            return qr.code
        return None


class VehicleCreateSerializer(serializers.ModelSerializer):
    """Create vehicle; qr_code created server-side."""

    class Meta:
        model = Vehicle
        fields = [
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
    contact_options = serializers.ListField(
        child=serializers.CharField(),
        help_text='Available options: call, chat, ticket',
    )
