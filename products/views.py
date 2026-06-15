from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import models

from .models import Product, Category
from .serializers import ProductSerializer, CategorySerializer, CategoryProductListSerializer
from .filters import ProductFilter


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        category = self.get_object()
        products = category.product_set.all()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['id', 'name', 'price', 'stock']
    ordering = ['-id']

    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Endpoint de búsqueda personalizado.
        Parámetros: q (query), category_id, price_min, price_max, in_stock
        """
        queryset = self.get_queryset()

        # Búsqueda textual
        query = request.query_params.get('q', '')
        if query:
            queryset = queryset.filter(
                models.Q(name__icontains=query) |
                models.Q(description__icontains=query) |
                models.Q(sku__icontains=query)
            )

        # Filtro por categoría
        category_id = request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)

        # Filtro por precio mínimo
        price_min = request.query_params.get('price_min')
        if price_min:
            queryset = queryset.filter(price__gte=float(price_min))

        # Filtro por precio máximo
        price_max = request.query_params.get('price_max')
        if price_max:
            queryset = queryset.filter(price__lte=float(price_max))

        # Filtro por disponibilidad
        in_stock = request.query_params.get('in_stock')
        if in_stock and in_stock.lower() == 'true':
            queryset = queryset.filter(stock__gt=0)

        # Ordenamiento
        ordering = request.query_params.get('ordering', '-id')
        queryset = queryset.order_by(ordering)

        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        """
        Obtiene productos relacionados (misma categoría).
        """
        product = self.get_object()
        related = Product.objects.filter(
            categories__in=product.categories.all()
        ).exclude(id=product.id).distinct()[:5]
        serializer = self.get_serializer(related, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Obtiene productos destacados (opcional: stock > 5 y precio < promedio).
        """
        featured_products = self.get_queryset().filter(stock__gte=5)[:10]
        serializer = self.get_serializer(featured_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_drop(self, request):
        """ Endpoint directo para traer productos por Drop """
        drop_id = request.query_params.get('drop_id')
        if not drop_id:
            return Response({'error': 'drop_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)
            
        queryset = self.get_queryset().filter(drop_id=drop_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
