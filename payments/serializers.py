from rest_framework import serializers

from orders.models import Order
from .models import PaymentTransaction


class PaymentTransactionSerializer(serializers.ModelSerializer):
    order_total = serializers.DecimalField(source='order.total', max_digits=10, decimal_places=2, read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'order', 'order_total', 'provider', 'provider_display', 'payment_method',
            'amount', 'status', 'status_display', 'external_reference', 'transaction_id',
            'checkout_url', 'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'status', 'external_reference', 'transaction_id', 'checkout_url',
            'processed_at', 'created_at', 'updated_at'
        ]


class CreatePaymentSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=PaymentTransaction.ProviderChoices.choices)
    payment_method = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context['request']
        try:
            order = Order.objects.get(id=attrs['order_id'], user=request.user)
        except Order.DoesNotExist as exc:
            raise serializers.ValidationError({'order_id': 'La orden no existe o no pertenece al usuario.'}) from exc

        if order.total <= 0:
            raise serializers.ValidationError({'order_id': 'La orden no tiene un total válido.'})

        attrs['order'] = order
        return attrs


class WebhookPaymentSerializer(serializers.Serializer):
    external_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    transaction_id = serializers.CharField(max_length=120, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=PaymentTransaction.StatusChoices.choices)
    payload = serializers.JSONField(required=False)


class CashPaymentConfirmSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    payment_method = serializers.CharField(max_length=50, required=False, allow_blank=True, default='cash_on_delivery')
