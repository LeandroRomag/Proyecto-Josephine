from django.contrib import admin
from .models import ShippingZone, PickupPoint, Address


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'shipping_cost', 'estimated_days', 'is_active']
    list_filter = ['is_active', 'estimated_days']
    search_fields = ['name']
    fieldsets = (
        ('Información General', {
            'fields': ('name', 'shipping_cost', 'estimated_days', 'is_active')
        }),
        ('Polígono GeoJSON', {
            'fields': ('polygon_geojson',),
            'classes': ('collapse',),
            'description': 'Formato GeoJSON FeatureCollection con polígono(s) de la zona.'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PickupPoint)
class PickupPointAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'zone', 'latitude', 'longitude', 'is_active']
    list_filter = ['is_active', 'zone']
    search_fields = ['name', 'address', 'phone', 'email']
    fieldsets = (
        ('Información General', {
            'fields': ('name', 'address', 'zone')
        }),
        ('Ubicación', {
            'fields': ('latitude', 'longitude')
        }),
        ('Contacto', {
            'fields': ('phone', 'email', 'opening_hours')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_address', 'zone', 'is_valid', 'created_at']
    list_filter = ['is_valid', 'zone', 'created_at']
    search_fields = ['full_address']
    readonly_fields = ['zone', 'is_valid', 'created_at']
