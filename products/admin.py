from django.contrib import admin
from .models import Category, Product, ProductColor, ProductGalleryImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'product_count']
    search_fields = ['name']

    def product_count(self, obj):
        return obj.product_set.count()
    product_count.short_description = 'Productos'


class ProductInlineAdmin(admin.TabularInline):
    model = Product.categories.through
    extra = 1


class ProductColorInline(admin.TabularInline):
    model = ProductColor
    extra = 1


class ProductGalleryImageInline(admin.TabularInline):
    model = ProductGalleryImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'sku', 'price', 'stock', 'get_categories']
    list_filter = ['categories', 'price', 'stock']
    search_fields = ['name', 'sku', 'description']
    filter_horizontal = ['categories']
    readonly_fields = ['id']
    inlines = [ProductColorInline, ProductGalleryImageInline]
    fieldsets = (
        ('Información General', {
            'fields': ('id', 'name', 'sku', 'description')
        }),
        ('Precio y Stock', {
            'fields': ('price', 'stock')
        }),
        ('Categorías', {
            'fields': ('categories',)
        }),
    )

    def get_categories(self, obj):
        return ', '.join([cat.name for cat in obj.categories.all()])
    get_categories.short_description = 'Categorías'
