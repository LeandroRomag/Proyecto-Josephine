from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShippingZoneViewSet, PickupPointViewSet, AddressViewSet

router = DefaultRouter()
router.register('zones', ShippingZoneViewSet, basename='zone')
router.register('pickup-points', PickupPointViewSet, basename='pickup-point')
router.register('addresses', AddressViewSet, basename='address')

urlpatterns = [
    path('', include(router.urls)),
]
