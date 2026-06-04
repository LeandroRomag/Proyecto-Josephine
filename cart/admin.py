from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'get_item_count', 'get_total', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email']
    inlines = [CartItemInline]
    readonly_fields = ['created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.get_item_count()
    get_item_count.short_description = 'Items'

    def get_total(self, obj):
        return f"${obj.get_total():.2f}"
    get_total.short_description = 'Total'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'cart', 'product', 'quantity', 'get_item_total']
    list_filter = ['added_at']
    search_fields = ['product__name', 'cart__user__email']

    def get_item_total(self, obj):
        return f"${obj.get_item_total():.2f}"
    get_item_total.short_description = 'Total'
