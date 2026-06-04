from django.db import models
from django.conf import settings
from products.models import Product, ProductVariant


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart', null=True, blank=True)
    session_key = models.CharField(max_length=40, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        owner = self.user or self.session_key or f'Cart {self.id}'
        return f"Cart {self.id} - {owner}"

    def get_total(self):
        return sum(item.get_item_total() for item in self.items.all())

    def get_item_count(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product', 'variant')

    def __str__(self):
        variant = f" / {self.variant.size}" if self.variant and self.variant.size else ''
        return f"{self.product.name}{variant} x{self.quantity}"

    def get_item_total(self):
        return self.product.price * self.quantity
