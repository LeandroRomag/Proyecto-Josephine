from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from products.models import Product, Category
from django.utils import timezone


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Promotion(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Porcentaje (%)'),
        ('fixed', 'Monto fijo ($)'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=50, unique=True, db_index=True, blank=True, null=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Máximo descuento en pesos (solo para porcentaje)"
    )
    min_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Monto mínimo para aplicar la promoción"
    )
    products = models.ManyToManyField(Product, blank=True, help_text="Usar para promos automáticas sobre productos concretos")
    categories = models.ManyToManyField(Category, blank=True, help_text="Usar para promos automáticas por categoría")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    max_uses = models.IntegerField(null=True, blank=True, help_text="Dejar vacío para usos ilimitados")
    current_uses = models.IntegerField(default=0, help_text="Usos actuales (se incrementa automáticamente)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.code or 'Sin código'})"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        else:
            self.code = None
        super().save(*args, **kwargs)

    def is_valid(self):
        """Verifica si la promoción está activa y dentro de fechas válidas."""
        now = timezone.now()
        if not self.is_active or self.is_deleted:
            return False
        if self.end_date and now > self.end_date:
            return False
        if now < self.start_date:
            return False
        if self.max_uses and self.current_uses >= self.max_uses:
            return False
        return True

    def apply_discount(self, subtotal, cart_items=None, ignore_targets=False):
        """
        Aplica el descuento al subtotal.
        Retorna: (descuento_aplicado, total_con_descuento)
        """
        if not self.is_valid():
            return 0, subtotal

        if subtotal < self.min_order_value:
            return 0, subtotal

        # Verificar si la promoción aplica a los productos en el carrito, salvo que se fuerce por código.
        if cart_items and not ignore_targets and (self.products.exists() or self.categories.exists()):
            has_applicable_products = False
            for item in cart_items:
                if self.products.filter(id=item.product_id).exists():
                    has_applicable_products = True
                    break
                if self.categories.filter(product=item.product).exists():
                    has_applicable_products = True
                    break
            if not has_applicable_products:
                return 0, subtotal

        if self.discount_type == 'percentage':
            discount = (subtotal * self.discount_value) / 100
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        else:  # fixed
            discount = self.discount_value

        discount = min(discount, subtotal)
        return discount, subtotal - discount

    def increment_uses(self):
        """Incrementa los usos de la promoción."""
        self.current_uses += 1
        self.save()
