from django.db import models


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Category(models.Model):
    name = models.CharField(max_length=200)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    def __str__(self):
        return self.name


class Drop(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='drops/%Y/%m/', blank=True, null=True)
    release_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    categories = models.ManyToManyField(Category, blank=True)
    drop = models.ForeignKey(Drop, on_delete=models.SET_NULL, blank=True, null=True, related_name='products')
    is_deleted = models.BooleanField(default=False)
    image = models.ImageField(upload_to='products/%Y/%m/%d/', blank=True, null=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    def __str__(self):
        return self.name

    @property
    def primary_image_url(self):
        if self.image:
            try:
                return self.image.url
            except Exception:
                pass

        first_gallery_image = getattr(self, 'gallery_images_cache', None)
        if first_gallery_image is not None:
            if first_gallery_image:
                try:
                    return first_gallery_image[0].image.url
                except Exception:
                    return ''

        first_related_image = self.gallery_images.order_by('position').first()
        if first_related_image and first_related_image.image:
            try:
                return first_related_image.image.url
            except Exception:
                return ''

        return ''


def _gallery_image_upload_to(instance, filename):
    # Use product id and position in path to avoid filename collisions between different slots
    # Keep original extension, but prefix with a unique token (timestamp + position) to reduce collisions
    import time
    base, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    ts = int(time.time() * 1000)
    product_id = getattr(instance.product, 'id', 'new')
    position = getattr(instance, 'position', 0) or 0
    name = f"img_{ts}_{position}.{ext}" if ext else f"img_{ts}_{position}"
    return f'products/{product_id}/gallery/{position}/{name}'


class ProductGalleryImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to=_gallery_image_upload_to)
    position = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['position', 'id']
        unique_together = ('product', 'position')

    def __str__(self):
        return f'{self.product.name} - foto {self.position}'


class ProductColor(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='colors')
    color_hex = models.CharField(max_length=7)

    COLOR_NAMES = {
        '#000000': 'Negro',
        '#1f1f1f': 'Grafito',
        '#3a3a3a': 'Gris oscuro',
        '#808080': 'Gris',
        '#c0c0c0': 'Plateado',
        '#ffffff': 'Blanco',
        '#f5f5dc': 'Beige',
        '#f3e5ab': 'Crema',
        '#d2b48c': 'Arena',
        '#a52a2a': 'Marrón',
        '#8b4513': 'Camel',
        '#ff0000': 'Rojo',
        '#ff7f50': 'Coral',
        '#ff8c00': 'Naranja',
        '#ffd700': 'Dorado',
        '#ffff00': 'Amarillo',
        '#98fb98': 'Verde claro',
        '#008000': 'Verde',
        '#20b2aa': 'Turquesa',
        '#00ffff': 'Cian',
        '#87ceeb': 'Celeste',
        '#0000ff': 'Azul',
        '#4169e1': 'Azul rey',
        '#4b0082': 'Índigo',
        '#800080': 'Violeta',
        '#ff00ff': 'Fucsia',
        '#ff69b4': 'Rosa',
        '#d98bb0': 'Rosa empolvado',
    }

    @property
    def display_name(self):
        normalized = (self.color_hex or '').strip().lower()
        if not normalized:
            return 'Color'
        if not normalized.startswith('#'):
            normalized = f'#{normalized}'
        return self.COLOR_NAMES.get(normalized, 'Color personalizado')

    class Meta:
        unique_together = ('product', 'color_hex')

    def __str__(self):
        return f'{self.product.name} - {self.display_name}'


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    # Reference the real color row for this product
    color = models.ForeignKey(ProductColor, on_delete=models.PROTECT, related_name='variants')
    size = models.CharField(max_length=64, blank=True, null=True)
    stock = models.IntegerField(default=0)

    class Meta:
        unique_together = ('product', 'color', 'size')

    def __str__(self):
        size = self.size or '-'
        return f'{self.product.name} / {self.color.display_name} / {size} ({self.stock})'
