from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order


class Command(BaseCommand):
    help = 'Oculta lógicamente órdenes finalizadas con antigüedad mayor al umbral en horas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Cantidad de horas desde la última actualización para ocultar órdenes finalizadas.',
        )

    def handle(self, *args, **options):
        hours = max(1, int(options['hours']))
        cutoff = timezone.now() - timedelta(hours=hours)

        queryset = Order.objects.filter(
            status=Order.StatusChoices.DELIVERED,
            is_deleted=False,
            updated_at__lte=cutoff,
        )

        affected = queryset.update(is_deleted=True, updated_at=timezone.now())

        self.stdout.write(
            self.style.SUCCESS(
                f'Órdenes finalizadas ocultadas lógicamente: {affected}. Umbral: {hours} hora(s).'
            )
        )
