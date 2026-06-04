from django.contrib import admin

from .models import Order, OrderItem, ProductReservation


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'variant_size', 'quantity']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'payment_status', 'total', 'shipping_cost', 'grand_total', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['user__email', 'notes']
    inlines = [OrderItemInline]
    readonly_fields = ['created_at', 'updated_at', 'grand_total']
    fieldsets = (
        ('Información General', {
            'fields': ('user', 'status', 'payment_status', 'total', 'shipping_cost', 'grand_total')
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductReservation)
class ProductReservationAdmin(admin.ModelAdmin):
    list_display = ['id', 'variant', 'quantity', 'user', 'is_active', 'expires_at', 'created_at']
    list_filter = ['is_active', 'created_at', 'expires_at']
    search_fields = ['user__email', 'variant__product__name']
    readonly_fields = ['created_at', 'expires_at']
