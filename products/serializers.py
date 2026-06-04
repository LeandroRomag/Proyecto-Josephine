from rest_framework import serializers
from .models import Product, Category, ProductColor


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class ProductColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductColor
        fields = ['id', 'color_hex']


class ProductSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)
    colors = ProductColorSerializer(many=True, read_only=True)
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        many=True,
        write_only=True,
        source='categories'
    )

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'description', 'price', 'stock', 'categories', 'colors', 'category_ids']


class CategoryProductListSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'product_count']

    def get_product_count(self, obj):
        return obj.product_set.count()
