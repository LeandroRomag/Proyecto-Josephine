from django.db.models import Sum
from django.utils import timezone

from django.db import transaction

from products.models import ProductVariant

from .models import ProductReservation


def get_active_variant_reservation_totals(variant_ids, now=None, exclude_user=None, exclude_session_key=None):
    now = now or timezone.now()
    variant_ids = list(variant_ids or [])
    if not variant_ids:
        return {}

    queryset = ProductReservation.objects.filter(
        variant_id__in=variant_ids,
        is_active=True,
        expires_at__gt=now,
    )
    if exclude_user is not None or exclude_session_key:
        queryset = queryset.exclude(user=exclude_user, session_key=exclude_session_key or '')

    rows = queryset.values('variant_id').annotate(total=Sum('quantity'))
    return {
        row['variant_id']: int(row['total'] or 0)
        for row in rows
    }


def get_variant_available_stock(variant, now=None, exclude_user=None, exclude_session_key=None):
    if variant is None:
        return 0

    totals = get_active_variant_reservation_totals(
        [variant.id],
        now=now,
        exclude_user=exclude_user,
        exclude_session_key=exclude_session_key,
    )
    reserved = int(totals.get(variant.id, 0) or 0)
    return max(0, int(variant.stock or 0) - reserved)


def restore_order_stock(order):
    if order is None:
        return 0, 0

    restored_items = 0
    restored_reservations = 0

    with transaction.atomic():
        locked_order = order.__class__.objects.select_for_update().get(id=order.id)
        for item in locked_order.orderitem_set.select_related('variant', 'product').all():
            variant = item.variant or item.product.variants.first()
            if not variant:
                continue

            locked_variant = ProductVariant.objects.select_for_update().get(id=variant.id)
            locked_variant.stock = (locked_variant.stock or 0) + item.quantity
            locked_variant.save(update_fields=['stock'])
            restored_items += 1

            restored_reservations += ProductReservation.objects.filter(
                order=locked_order,
                variant=variant,
                is_active=True,
            ).update(is_active=False)

    return restored_items, restored_reservations