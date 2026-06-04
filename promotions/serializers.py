from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import Promotion
from products.models import Product, Category


class PromotionSerializer(serializers.ModelSerializer):
    product_ids = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        many=True,
        write_only=True,
        source='products'
    )
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        many=True,
        write_only=True,
        source='categories'
    )
    products = serializers.StringRelatedField(many=True, read_only=True)
    categories = serializers.StringRelatedField(many=True, read_only=True)
    is_valid_now = serializers.SerializerMethodField()

    class Meta:
        model = Promotion
        fields = [
            'id', 'name', 'description', 'code', 'discount_type', 'discount_value',
            'max_discount_amount', 'min_order_value', 'product_ids', 'category_ids',
            'products', 'categories', 'start_date', 'end_date', 'is_active', 'max_uses',
            'current_uses', 'is_valid_now', 'created_at', 'updated_at'
        ]
        read_only_fields = ['current_uses', 'created_at', 'updated_at', 'products', 'categories']

    def get_is_valid_now(self, obj):
        return obj.is_valid()


class PromotionApplySerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_code(self, value):
        value = (value or '').strip().upper()
        if value:
            try:
                Promotion.objects.get(code__iexact=value)
            except Promotion.DoesNotExist:
                raise serializers.ValidationError("Código de promoción no válido.")
        return value
