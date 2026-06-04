from rest_framework import serializers
from .models import ShippingZone, PickupPoint, Address


class ShippingZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingZone
        fields = ['id', 'name', 'shipping_cost', 'estimated_days', 'is_active']


class ShippingZoneDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingZone
        fields = ['id', 'name', 'polygon_geojson', 'shipping_cost', 'estimated_days', 'is_active']


class PickupPointSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='zone.name', read_only=True)

    class Meta:
        model = PickupPoint
        fields = [
            'id', 'name', 'address', 'latitude', 'longitude', 'phone', 'email',
            'opening_hours', 'zone', 'zone_name', 'is_active'
        ]


class AddressSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    shipping_cost = serializers.DecimalField(
        source='zone.shipping_cost',
        read_only=True,
        max_digits=10,
        decimal_places=2
    )
    estimated_days = serializers.IntegerField(
        source='zone.estimated_days',
        read_only=True
    )

    class Meta:
        model = Address
        fields = [
            'id', 'full_address', 'latitude', 'longitude', 'zone', 'zone_name',
            'shipping_cost', 'estimated_days', 'is_valid', 'created_at'
        ]
        read_only_fields = ['is_valid', 'zone', 'shipping_cost', 'estimated_days', 'created_at']


class ValidateAddressSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=500)
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)


class ShippingOptionsSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
