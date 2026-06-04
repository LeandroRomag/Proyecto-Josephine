from django.contrib import admin

from .models import SiteSettings, SiteText


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'contact_whatsapp')


@admin.register(SiteText)
class SiteTextAdmin(admin.ModelAdmin):
    list_display = ('key', 'description')
    search_fields = ('key', 'text')
    ordering = ('key',)
