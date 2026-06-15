from rest_framework import serializers
from .models import Cart, CartItem
from products.models import Product, ProductVariant

class ProductCartSerializer(serializers.ModelSerializer):
    # 🌟 CORRECCIÓN: Apuntamos la imagen a la propiedad que resuelve la galería
    image = serializers.CharField(source='primary_image_url', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'stock', 'image']


# 🌟 NUEVO: Serializador interno para descomponer la variante en el carrito
class VariantCartSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='color.display_name', read_only=True)
    color_hex = serializers.CharField(source='color.color_hex', read_only=True)

    class Meta:
        model = ProductVariant
        fields = ['id', 'size', 'display_name', 'color_hex']


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductCartSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    # 🌟 CORRECCIÓN: Relacionamos la variante y su ID de escritura
    variant = VariantCartSerializer(read_only=True)
    variant_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    item_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        # 🌟 CORRECCIÓN: Añadimos 'variant' y 'variant_id' a los campos
        fields = ['id', 'product', 'product_id', 'variant', 'variant_id', 'quantity', 'item_total']

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