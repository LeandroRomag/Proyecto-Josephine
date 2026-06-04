from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from orders.stock import restore_order_stock


class Command(BaseCommand):
    help = 'Cancela órdenes pendientes vencidas, restaura stock y marca el pago como cancelado.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=60,
            help='Cantidad de minutos de antigüedad para considerar una orden pendiente como vencida.',
        )

    def handle(self, *args, **options):
        minutes = max(1, int(options['minutes']))
        cutoff = timezone.now() - timedelta(minutes=minutes)

        pending_orders = (
            Order.objects.select_related('user')
            .prefetch_related('orderitem_set__variant', 'orderitem_set__product')
            .filter(
                status=Order.StatusChoices.PENDING,
                payment_status=Order.PaymentStatusChoices.PENDING,
                created_at__lte=cutoff,
            )
            .order_by('created_at')
        )

        processed = 0
        restored_items = 0
        cancelled_reservations = 0

        for order in pending_orders:
            with transaction.atomic():
                locked_order = Order.objects.select_for_update().get(id=order.id)
                if locked_order.status != Order.StatusChoices.PENDING or locked_order.payment_status != Order.PaymentStatusChoices.PENDING:
                    continue

                items_count, reservations_count = restore_order_stock(locked_order)
                restored_items += items_count
                cancelled_reservations += reservations_count

                locked_order.payment_status = Order.PaymentStatusChoices.FAILED
                locked_order.status = Order.StatusChoices.CANCELLED
                locked_order.save(update_fields=['payment_status', 'status', 'updated_at'])
                processed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Órdenes canceladas: {processed}. Items restaurados: {restored_items}. Reservas desactivadas: {cancelled_reservations}.'
            )
        )
