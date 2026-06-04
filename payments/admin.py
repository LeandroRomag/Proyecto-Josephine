from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'order', 'provider', 'payment_method', 'amount', 'status', 'created_at']
    list_filter = ['provider', 'status', 'created_at']
    search_fields = ['external_reference', 'transaction_id', 'order__id', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'processed_at']
