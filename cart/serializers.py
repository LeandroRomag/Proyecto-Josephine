from rest_framework import serializers
from .models import Cart, CartItem
from products.models import Product


class ProductCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'stock']


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductCartSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    item_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'item_total']

    def get_item_total(self, obj):
        return float(obj.get_item_total())


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'total', 'item_count', 'created_at', 'updated_at']

    def get_total(self, obj):
        return float(obj.get_total())

    def get_item_count(self, obj):
        return obj.get_item_count()
