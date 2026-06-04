from django.conf import settings
from django.db import models

from orders.models import Order


class PaymentTransaction(models.Model):
    class ProviderChoices(models.TextChoices):
        MERCADO_PAGO = 'mercado_pago', 'Mercado Pago'
        CASH = 'cash', 'Efectivo'

    class StatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        APPROVED = 'approved', 'Aprobado'
        REJECTED = 'rejected', 'Rechazado'
        CANCELLED = 'cancelled', 'Cancelado'
        REFUNDED = 'refunded', 'Reintegrado'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    provider = models.CharField(max_length=50, choices=ProviderChoices.choices)
    payment_method = models.CharField(max_length=50, default='unknown')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=50, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    external_reference = models.CharField(max_length=120, blank=True, default='')
    transaction_id = models.CharField(max_length=120, blank=True, default='')
    checkout_url = models.URLField(blank=True, default='')
    provider_payload = models.JSONField(blank=True, null=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_provider_display()} - Order #{self.order_id or 'Guest'} - {self.status}"

    @property
    def is_successful(self):
        return self.status == self.StatusChoices.APPROVED
