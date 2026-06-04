from django.contrib import admin
from .models import Promotion


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'code', 'discount_type', 'discount_value', 'is_active', 'uses_display', 'start_date']
    list_filter = ['is_active', 'discount_type', 'start_date', 'end_date']
    search_fields = ['name', 'code', 'description']
    filter_horizontal = ['products', 'categories']
    fieldsets = (
        ('Información General', {
            'fields': ('name', 'description', 'code')
        }),
        ('Descuento', {
            'fields': ('discount_type', 'discount_value', 'max_discount_amount')
        }),
        ('Restricciones', {
            'fields': ('min_order_value', 'products', 'categories')
        }),
        ('Validez', {
            'fields': ('is_active', 'start_date', 'end_date')
        }),
        ('Límites', {
            'fields': ('max_uses', 'current_uses')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['current_uses', 'created_at', 'updated_at']

    def uses_display(self, obj):
        if obj.max_uses:
            return f"{obj.current_uses}/{obj.max_uses}"
        return f"{obj.current_uses} (ilimitado)"
    uses_display.short_description = 'Usos'
