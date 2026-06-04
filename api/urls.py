from django.urls import path, include
from django.http import JsonResponse

def ping(request):
    return JsonResponse({'ok': True})

urlpatterns = [
    path('ping/', ping),
    path('products/', include('products.urls')),
    path('admin/', include('orders.urls')),
]
