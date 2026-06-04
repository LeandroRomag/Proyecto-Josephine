from decimal import Decimal

from django.db.models import Count, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from payments.models import PaymentTransaction
from products.models import Product
from .models import Order, OrderItem
from .serializers import (
    AdminOrderMetricsSerializer,
    OrderSerializer,
    OrderStatusUpdateSerializer,
)


class AdminOrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]
    queryset = Order.objects.select_related('user').prefetch_related('orderitem_set__product').all().order_by('-created_at')

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        payment_status_filter = self.request.query_params.get('payment_status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if payment_status_filter:
            queryset = queryset.filter(payment_status=payment_status_filter)
        return queryset

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        orders = self.get_queryset()
        total_orders = orders.count()
        pending_orders = orders.filter(status=Order.StatusChoices.PENDING).count()
        confirmed_orders = orders.filter(status=Order.StatusChoices.CONFIRMED).count()
        delivered_orders = orders.filter(status=Order.StatusChoices.DELIVERED).count()
        cancelled_orders = orders.filter(status=Order.StatusChoices.CANCELLED).count()

        gross_revenue = orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
        paid_revenue = orders.filter(payment_status=Order.PaymentStatusChoices.PAID).aggregate(total=Sum('total'))['total'] or Decimal('0')

        top_products = (
            OrderItem.objects
            .values('product_id', 'product__name')
            .annotate(total_sold=Sum('quantity'))
            .order_by('-total_sold')[:5]
        )

        recent_orders = orders[:10]

        metrics = {
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'confirmed_orders': confirmed_orders,
            'delivered_orders': delivered_orders,
            'cancelled_orders': cancelled_orders,
            'gross_revenue': gross_revenue,
            'paid_revenue': paid_revenue,
            'top_products': [
                {
                    'product_id': item['product_id'],
                    'product_name': item['product__name'],
                    'total_sold': item['total_sold'] or 0,
                }
                for item in top_products
            ],
            'recent_orders': OrderSerializer(recent_orders, many=True).data,
        }
        serializer = AdminOrderMetricsSerializer(metrics)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order.status = serializer.validated_data['status']
        if 'payment_status' in serializer.validated_data:
            order.payment_status = serializer.validated_data['payment_status']
        if 'shipping_cost' in serializer.validated_data:
            order.shipping_cost = serializer.validated_data['shipping_cost']
        if 'notes' in serializer.validated_data:
            order.notes = serializer.validated_data['notes']
        order.save(update_fields=['status', 'payment_status', 'shipping_cost', 'notes', 'updated_at'])

        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        order = self.get_object()
        order.payment_status = Order.PaymentStatusChoices.PAID
        order.save(update_fields=['payment_status', 'updated_at'])

        PaymentTransaction.objects.filter(order=order).update(status=PaymentTransaction.StatusChoices.APPROVED)
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)
