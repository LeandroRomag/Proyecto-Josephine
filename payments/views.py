from decimal import Decimal
import json
import os
from uuid import uuid4

from django.conf import settings
from django.utils import timezone
from django.db import transaction as db_transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from cart.models import Cart
from orders.models import Order, ProductReservation
from orders.stock import restore_order_stock
from products.models import ProductVariant

from .models import PaymentTransaction
from .serializers import (
    CashPaymentConfirmSerializer,
    CreatePaymentSerializer,
    PaymentTransactionSerializer,
    WebhookPaymentSerializer,
)


MP_PAYMENT_STATUS_MAP = {
    'approved': PaymentTransaction.StatusChoices.APPROVED,
    'authorized': PaymentTransaction.StatusChoices.APPROVED,
    'in_process': PaymentTransaction.StatusChoices.PENDING,
    'pending': PaymentTransaction.StatusChoices.PENDING,
    'rejected': PaymentTransaction.StatusChoices.REJECTED,
    'cancelled': PaymentTransaction.StatusChoices.CANCELLED,
    'refunded': PaymentTransaction.StatusChoices.REFUNDED,
    'charged_back': PaymentTransaction.StatusChoices.REFUNDED,
}


class PaymentTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PaymentTransaction.objects.filter(user=self.request.user).select_related('order')

    @action(detail=False, methods=['post'])
    def create_payment(self, request):
        serializer = CreatePaymentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        order = serializer.validated_data['order']
        provider = serializer.validated_data['provider']
        payment_method = serializer.validated_data.get('payment_method') or (
            'mercado_pago_card' if provider == PaymentTransaction.ProviderChoices.MERCADO_PAGO else 'cash_on_delivery'
        )

        external_reference = f"JOSEPHINE-{order.id}-{uuid4().hex[:12]}"
        checkout_url = ''
        if provider == PaymentTransaction.ProviderChoices.MERCADO_PAGO:
            checkout_url = f"https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id={external_reference}"

        transaction = PaymentTransaction.objects.create(
            user=request.user if request.user.is_authenticated else None,
            order=order,
            provider=provider,
            payment_method=payment_method,
            amount=order.total,
            status=PaymentTransaction.StatusChoices.PENDING,
            external_reference=external_reference,
            checkout_url=checkout_url,
            provider_payload={
                'source': 'api',
                'order_total': str(order.total),
                'created_at': timezone.now().isoformat(),
                'session_key': request.session.session_key or '',
                'user_id': request.user.id if request.user.is_authenticated else None,
            },
        )

        return Response(
            PaymentTransactionSerializer(transaction).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'])
    def cash(self, request):
        return Response(
            {'detail': 'Pago en efectivo deshabilitado. Usá Mercado Pago.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def webhook(self, request):
        webhook_data = _build_mp_webhook_data(request)
        if webhook_data is None:
            return Response(
                {'detail': 'Payload de webhook inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        external_reference = webhook_data.get('external_reference')
        transaction_id = webhook_data.get('transaction_id')
        new_status = webhook_data.get('status')
        payload = webhook_data.get('payload')

        transaction = PaymentTransaction.objects.filter(
            external_reference=external_reference,
        ).first()
        if transaction is None and transaction_id:
            transaction = PaymentTransaction.objects.filter(transaction_id=transaction_id).first()

        if transaction is None:
            return Response(
                {'detail': 'Transacción no encontrada.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        merged_payload = transaction.provider_payload or {}
        if isinstance(payload, dict):
            merged_payload.update(payload)

        transaction.status = new_status
        transaction.transaction_id = transaction_id or transaction.transaction_id
        transaction.provider_payload = merged_payload
        transaction.processed_at = timezone.now()
        transaction.save(update_fields=['status', 'transaction_id', 'provider_payload', 'processed_at', 'updated_at'])

        if transaction.order_id:
            if new_status == PaymentTransaction.StatusChoices.APPROVED:
                _finalize_approved_order_payment(transaction)
            elif new_status in (PaymentTransaction.StatusChoices.REJECTED, PaymentTransaction.StatusChoices.CANCELLED):
                _mark_order_payment_failed(transaction.order)

        return Response(PaymentTransactionSerializer(transaction).data)


def _build_mp_webhook_data(request):
    payload = {}

    if isinstance(request.data, dict):
        payload.update(request.data)

    query_params = request.query_params.dict()
    payload.update(query_params)

    external_reference = payload.get('external_reference') or payload.get('externalReference')
    transaction_id = payload.get('transaction_id') or payload.get('id') or payload.get('data.id')
    raw_status = payload.get('status')
    topic = (payload.get('topic') or payload.get('type') or '').lower()

    mp_payment = None
    if (not external_reference or not raw_status) and transaction_id and topic in {'payment', 'payments', ''}:
        mp_payment = _fetch_mercado_pago_payment(transaction_id)

    if mp_payment:
        payload['payload'] = mp_payment
        external_reference = external_reference or mp_payment.get('external_reference')
        transaction_id = transaction_id or mp_payment.get('id') or mp_payment.get('transaction_id')
        raw_status = raw_status or mp_payment.get('status')

    if not external_reference or not raw_status:
        return None

    normalized_status = MP_PAYMENT_STATUS_MAP.get(str(raw_status).lower())
    if not normalized_status:
        return None

    return {
        'external_reference': external_reference,
        'transaction_id': transaction_id,
        'status': normalized_status,
        'payload': payload.get('payload') or payload,
    }


def _fetch_mercado_pago_payment(payment_id):
    access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '') or os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')
    if not access_token:
        return None

    req = urllib_request.Request(
        f'https://api.mercadopago.com/v1/payments/{payment_id}',
        headers={'Authorization': f'Bearer {access_token}'},
        method='GET',
    )

    try:
        with urllib_request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def _consume_order_reservations(order, session_key='', user=None):
    with db_transaction.atomic():
        for item in order.orderitem_set.select_related('variant', 'product').all():
            variant = item.variant or item.product.variants.first()
            if not variant:
                raise ValueError(f'{item.product.name} no tiene variante válida.')

            # Prefer reservations explicitly linked to the order (locked_by_order).
            reservation = ProductReservation.objects.select_for_update().filter(
                order=order,
                variant=variant,
                is_active=True,
            ).first()

            # Fallback to session/user-based reservation if order-linked not found.
            if reservation is None:
                reservation = ProductReservation.objects.select_for_update().filter(
                    variant=variant,
                    user=user,
                    session_key=session_key or '',
                    is_active=True,
                ).first()

            if reservation is None:
                raise ValueError(f'No hay reserva válida para {item.product.name}.')

            # Adjust or consume the reservation quantity
            if reservation.quantity < item.quantity:
                raise ValueError(f'Reserva insuficiente para {item.product.name}.')
            elif reservation.quantity == item.quantity:
                reservation.is_active = False
            else:
                reservation.quantity = reservation.quantity - item.quantity

            # Persist reservation changes
            reservation.save()

            locked_variant = ProductVariant.objects.select_for_update().get(id=variant.id)
            locked_variant.stock -= item.quantity
            locked_variant.save(update_fields=['stock'])


def _clear_cart_for_owner(order, session_key=''):
    if order.user_id:
        cart = Cart.objects.filter(user_id=order.user_id).first()
    else:
        cart = Cart.objects.filter(session_key=session_key or '').first()

    if cart:
        cart.items.all().delete()


def _finalize_approved_order_payment(payment_transaction):
    order = payment_transaction.order
    payload = payment_transaction.provider_payload or {}
    session_key = payload.get('session_key') or ''
    owner_user = order.user

    # Approve: simply mark the order/payment as paid and confirmed. Stock
    # was already decremented at checkout time.
    with db_transaction.atomic():
        locked_order = Order.objects.select_for_update().get(id=order.id)
        if locked_order.payment_status == Order.PaymentStatusChoices.PAID:
            return

        locked_order.payment_status = Order.PaymentStatusChoices.PAID
        locked_order.status = Order.StatusChoices.CONFIRMED
        locked_order.save(update_fields=['payment_status', 'status', 'updated_at'])

    _clear_cart_for_owner(order, session_key=session_key)


def _mark_order_payment_failed(order):
    if not order:
        return

    # If the order is already cancelled, nothing to do (idempotency).
    if order.status == Order.StatusChoices.CANCELLED:
        return

    # Restore stock for order items and mark order cancelled/failed.
    with db_transaction.atomic():
        locked_order = Order.objects.select_for_update().get(id=order.id)
        restore_order_stock(locked_order)
        locked_order.payment_status = Order.PaymentStatusChoices.FAILED
        locked_order.status = Order.StatusChoices.CANCELLED
        locked_order.save(update_fields=['payment_status', 'status', 'updated_at'])
