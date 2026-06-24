from django.db import models
from django.conf import settings
from products.models import Product, ProductVariant
from promotions.models import Promotion
from shipping.models import ShippingZone, PickupPoint


class Order(models.Model):
    class DeliveryMethodChoices(models.TextChoices):
        SHIPPING = 'shipping', 'Envío a domicilio'
        PICKUP = 'pickup', 'Retiro en tienda'

    class StatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        CONFIRMED = 'confirmed', 'Confirmado'
        REJECTED = 'rejected', 'Rechazada'
        PROCESSING = 'processing', 'Empaquetando'
        SHIPPED = 'shipped', 'En Camino'
        DELIVERED = 'delivered', 'Finalizado'
        CANCELLED = 'cancelled', 'Cancelado'

    class PaymentStatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        PAID = 'paid', 'Pagado'
        FAILED = 'failed', 'Fallido'
        REFUNDED = 'refunded', 'Reintegrado'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    products = models.ManyToManyField(Product, through='OrderItem')
    customer_name = models.CharField(max_length=200, blank=True, default='')
    customer_email = models.EmailField(max_length=255, blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    delivery_method = models.CharField(max_length=20, choices=DeliveryMethodChoices.choices, default=DeliveryMethodChoices.SHIPPING)
    delivery_province = models.CharField(max_length=100, blank=True, default='')
    delivery_city = models.CharField(max_length=100, blank=True, default='')
    delivery_address = models.CharField(max_length=500, blank=True, default='')
    delivery_latitude = models.FloatField(null=True, blank=True)
    delivery_longitude = models.FloatField(null=True, blank=True)
    shipping_zone = models.ForeignKey(ShippingZone, on_delete=models.SET_NULL, null=True, blank=True)
    pickup_point = models.ForeignKey(PickupPoint, on_delete=models.SET_NULL, null=True, blank=True)
    promotion = models.ForeignKey(Promotion, on_delete=models.SET_NULL, null=True, blank=True)
    promo_code = models.CharField(max_length=50, blank=True, default='')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=30, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    payment_status = models.CharField(max_length=30, choices=PaymentStatusChoices.choices, default=PaymentStatusChoices.PENDING)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default='')
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        owner = self.user or 'Guest'
        return f"Order #{self.id} - {owner}"

    @property
    def grand_total(self):
        return self.total + self.shipping_cost


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    variant_size = models.CharField(max_length=50, blank=True, default='')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def resolved_variant_size(self):
        if self.variant and self.variant.size:
            return self.variant.size
        return self.variant_size


class ProductReservation(models.Model):
    """Temporary hold on product variants during checkout (prevents race conditions)"""
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, default='')
    locked_by_order = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('variant', 'user', 'session_key')

    def __str__(self):
        owner = self.user or f'Guest:{self.session_key}'
        return f'Reservation: {self.variant} x{self.quantity} - {owner}'
