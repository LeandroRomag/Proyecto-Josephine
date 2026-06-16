# Panel Admin — Django (BY Josephine)

Bundle con templates + CSS para el panel de administración y el menú lateral
que se abre con el botón hamburguesa de la izquierda en el header.

## Estructura

```
templates/
  partials/side_menu.html      ← incluir en base.html
  admin/panel.html             ← /admin-panel/
  admin/product_new.html       ← /admin-panel/productos/nuevo/
  admin/category_new.html      ← /admin-panel/categorias/nueva/
static/
  css/admin.css                ← cargar en base.html
```

## 1. Cargar el CSS en `base.html`

```html
{% load static %}
<link rel="stylesheet" href="{% static 'css/admin.css' %}">
```

## 2. Incluir el menú lateral en `base.html`

Dentro del `<header>`, en la columna izquierda:

```html
<header class="site-header">
  <div class="header-left">
    {% include "partials/side_menu.html" %}
  </div>
  <a class="brand" href="{% url 'home' %}">BY Josephine</a>
  <div class="header-right">...</div>
</header>
```

El partial ya incluye el botón hamburguesa (`#menuToggle`), el panel
deslizante y el JS para abrir/cerrar. La sección **Administración** solo
se muestra a usuarios con `is_staff=True`.

## 3. URLs (`urls.py`)

```python
from django.urls import path
from . import views

urlpatterns = [
    # ... rutas existentes (home, catalog, login, register, etc.)
    path("admin-panel/", views.admin_panel, name="admin_panel"),
    path("admin-panel/productos/nuevo/", views.admin_product_new, name="admin_product_new"),
    path("admin-panel/categorias/nueva/", views.admin_category_new, name="admin_category_new"),
]
```

> Usamos `admin-panel/` para no chocar con `/admin/` de Django.

## 4. Vistas protegidas (`views.py`)

```python
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from .models import Category, Product
from .forms import ProductForm, CategoryForm  # tus ModelForms

staff_required = user_passes_test(lambda u: u.is_authenticated and u.is_staff)

@login_required
@staff_required
def admin_panel(request):
    return render(request, "admin/panel.html")

@login_required
@staff_required
def admin_product_new(request):
    saved = False
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            saved = True
    return render(request, "admin/product_new.html", {
        "categories": Category.objects.all(),
        "saved": saved,
    })

@login_required
@staff_required
def admin_category_new(request):
    saved = False
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            saved = True
    return render(request, "admin/category_new.html", {"saved": saved})
```

## 5. Roles

El menú usa `user.is_staff` para mostrar la sección Admin. Para más control,
podés usar grupos (`user.groups.filter(name='admin').exists()`) o un campo
`role` en el modelo de usuario.
