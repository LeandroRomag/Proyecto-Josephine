from rest_framework import serializers

from products.models import Product
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_price', 'variant_size', 'quantity']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(source='orderitem_set', many=True, read_only=True)
    user_email = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    grand_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'user_email', 'items', 'total', 'shipping_cost',
            'grand_total', 'status', 'status_display', 'payment_status',
            'payment_status_display', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.StatusChoices.choices)
    payment_status = serializers.ChoiceField(choices=Order.PaymentStatusChoices.choices, required=False)
    shipping_cost = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class AdminOrderMetricsSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    confirmed_orders = serializers.IntegerField()
    delivered_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()
    gross_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    top_products = serializers.ListField(child=serializers.DictField())
    recent_orders = serializers.ListField(child=serializers.DictField())
