# BY Josephine — Plantillas Django

Estructura lista para copiar a tu proyecto Django.

```
templates/
  base.html
  home.html
  partials/
    header.html
    footer.html
    product_card.html
static/
  css/styles.css
  img/        ← copiá acá hero-models.jpg y las fotos de productos
```

## 1) settings.py

```python
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    ...
}]

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
```

## 2) urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("carrito/", views.cart, name="cart"),
]
```

## 3) views.py (datos de ejemplo)

```python
from django.shortcuts import render

PRODUCTS = [
    {
        "id": 1,
        "name": "Top manga larga Olivia",
        "category": "Tops / Bodys",
        "image": "/static/img/product-top.jpg",
        "price_original": "38.900",
        "price_final": "19.450",
        "discount": 50,
        "sizes": ["XS", "S", "M", "L"],
        "colors": [
            {"name": "Negro", "hex": "#111"},
            {"name": "Crema", "hex": "#efe6d8"},
            {"name": "Rosa",  "hex": "#f5c6d6"},
        ],
        "free_shipping": True,
    },
    # ... resto de productos
]

def home(request):
    return render(request, "home.html", {"products": PRODUCTS})

def cart(request):
    return render(request, "cart.html")  # próximo paso
```

Si después usás un modelo `Product` en lugar de dicts, los nombres de campos del template son:
`name, category, image, price_original, price_final, discount, sizes, colors, free_shipping`.
