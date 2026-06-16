from django.urls import path, include
from django.views.generic.base import RedirectView
from django.contrib import admin
from django.conf import settings
from django.urls import re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', RedirectView.as_view(url='/ingresar/')),
    path('api/auth/', include('users.urls')),
    path('api/promotions/', include('promotions.urls')),
    path('api/shipping/', include('shipping.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/', include('api.urls')),
    path('api/cart/', include('cart.urls')),
    path('', include('web.urls')),
]

# Forzar a Django a servir archivos media en producción (Railway Volume)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]