from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django.utils import timezone

from .models import Promotion
from .serializers import PromotionSerializer, PromotionApplySerializer


class PromotionViewSet(viewsets.ModelViewSet):
    queryset = Promotion.objects.filter(is_active=True)
    serializer_class = PromotionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_staff:
            return Promotion.objects.all()
        return queryset

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Obtiene todas las promociones activas y válidas en el tiempo."""
        now = timezone.now()
        promotions = self.get_queryset().filter(
            start_date__lte=now
        )
        promotions = [p for p in promotions if p.is_valid()]
        serializer = self.get_serializer(promotions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def validate_code(self, request):
        """Valida un código de promoción y retorna los detalles."""
        code = request.data.get('code', '').strip()
        if not code:
            return Response(
                {'error': 'Código requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            promotion = Promotion.objects.get(code=code)
            if not promotion.is_valid():
                return Response(
                    {'error': 'Código de promoción expirado o inválido.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer = self.get_serializer(promotion)
            return Response(serializer.data)
        except Promotion.DoesNotExist:
            return Response(
                {'error': 'Código de promoción no encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get', 'post'])
    def apply(self, request):
        """
        Aplica una promoción a un monto.
        Body: { "code": "...", "subtotal": 100.00 }
        """
        data = request.data if request.method == 'POST' else request.query_params
        serializer = PromotionApplySerializer(data=data)
        if serializer.is_valid():
            code = (serializer.validated_data.get('code', '') or '').strip().upper()
            subtotal = serializer.validated_data['subtotal']

            if not code:
                return Response({
                    'promotion_id': None,
                    'discount_amount': 0.0,
                    'total_after_discount': float(subtotal),
                    'original_subtotal': float(subtotal),
                })

            try:
                promotion = Promotion.objects.filter(code__iexact=code).first() if code else None
                if promotion and promotion.is_valid():
                    discount, total = promotion.apply_discount(subtotal)
                    return Response({
                        'promotion_id': promotion.id,
                        'discount_amount': float(discount),
                        'total_after_discount': float(total),
                        'original_subtotal': float(subtotal),
                    })
                else:
                    return Response(
                        {'error': 'Promoción no válida.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Promotion.DoesNotExist:
                return Response(
                    {'error': 'Código de promoción no encontrado.'},
                    status=status.HTTP_404_NOT_FOUND
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
