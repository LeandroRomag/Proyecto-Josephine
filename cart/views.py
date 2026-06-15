from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Cart, CartItem
from .serializers import CartSerializer, CartItemSerializer
from products.models import Product


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    queryset = Cart.objects.all()

@action(detail=False, methods=['post'])
def add_item(self, request):
        cart, created = Cart.objects.get_or_create(user=request.user)
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id') # 🌟 CORRECCIÓN: Capturamos la variante
        quantity = request.data.get('quantity', 1)

        if not product_id:
            return Response({'error': 'product_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if product.stock < quantity:
            return Response({'error': 'Stock insuficiente'}, status=status.HTTP_400_BAD_REQUEST)

        # 🌟 CORRECCIÓN: Buscamos o creamos separando por producto Y variante exacta
        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant_id=variant_id, 
            defaults={'quantity': quantity}
        )

        if not item_created:
            cart_item.quantity += quantity
            cart_item.save()

        serializer = CartSerializer(cart)
        return Response(serializer.data)

@action(detail=False, methods=['post'])
def remove_item(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id') # 🌟 CORRECCIÓN: Saber qué variante borrar

        if not product_id:
            return Response({'error': 'product_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        # 🌟 CORRECCIÓN: Filtramos por item específico
        cart_item = get_object_or_404(CartItem, cart=cart, product_id=product_id, variant_id=variant_id)
        cart_item.delete()

        serializer = CartSerializer(cart)
        return Response(serializer.data)

@action(detail=False, methods=['post'])
def update_item(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id') # 🌟 CORRECCIÓN: Capturamos variante a actualizar
        quantity = request.data.get('quantity')

        if not product_id or quantity is None:
            return Response({'error': 'product_id y quantity requeridos'}, status=status.HTTP_400_BAD_REQUEST)

        # 🌟 CORRECCIÓN: Buscamos el registro preciso
        cart_item = get_object_or_404(CartItem, cart=cart, product_id=product_id, variant_id=variant_id)

        product = cart_item.product
        if product.stock < quantity:
            return Response({'error': 'Stock insuficiente'}, status=status.HTTP_400_BAD_REQUEST)

        if quantity <= 0:
            cart_item.delete()
        else:
            cart_item.quantity = quantity
            cart_item.save()

        serializer = CartSerializer(cart)
        return Response(serializer.data)