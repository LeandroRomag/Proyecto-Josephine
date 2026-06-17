from decimal import Decimal
import json
from django.utils import timezone
import re
import os
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from django.contrib import messages
from products.models import Drop
from products.forms import DropAdminForm
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from cart.models import Cart, CartItem
from orders.models import Order, OrderItem
from payments.models import PaymentTransaction
from products.models import Category, Drop, Product, ProductColor, ProductGalleryImage
from products.forms import CategoryAdminForm, ProductAdminForm
from products.forms import ProductVariantForm
from promotions.forms import PromotionAdminForm
from promotions.models import Promotion
from shipping.models import ShippingZone, PickupPoint
from shipping.serializers import ShippingZoneDetailSerializer
from orders.stock import get_active_variant_reservation_totals, get_variant_available_stock, restore_order_stock
from django.forms import inlineformset_factory
from products.models import ProductVariant
from django.forms import modelformset_factory
from django import forms
from core.models import SiteText
from users.models import User

from .forms import AddToCartForm, CartLineForm, CheckoutForm, FrontendLoginForm, FrontendRegisterForm, OrderLookupForm, PasswordResetConfirmForm, PasswordResetRequestForm, SiteSearchForm


AUTH_BACKEND = 'users.backends.EmailBackend'

ORDER_FLOW = [
    Order.StatusChoices.PENDING,
    Order.StatusChoices.CONFIRMED,
    Order.StatusChoices.PROCESSING,
    Order.StatusChoices.SHIPPED,
    Order.StatusChoices.DELIVERED,
]

ORDER_ADMIN_STATUSES = ORDER_FLOW + [Order.StatusChoices.REJECTED]
REJECTABLE_ORDER_STATUSES = {Order.StatusChoices.PENDING, Order.StatusChoices.CONFIRMED}


FALLBACK_IMAGES = [
    'https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1496747611176-843222e1e57c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=900&q=80',
]


HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
ITEMS_PER_PAGE = 10


def _validation_error_text(exc):
    messages = getattr(exc, 'messages', None)
    if messages:
        return ' '.join(str(message) for message in messages)
    return str(exc)


def _normalize_hex_color(value):
    cleaned = (value or '').strip()
    if not cleaned:
        return None
    if not cleaned.startswith('#'):
        cleaned = f'#{cleaned}'
    cleaned = cleaned.lower()
    if HEX_COLOR_RE.match(cleaned):
        return cleaned
    return None


def _build_pagination_querystring(request, *, exclude=None):
    exclude = set(exclude or ())
    params = request.GET.copy()
    for key in exclude:
        params.pop(key, None)
    return params.urlencode()


def _paginate_queryset(request, queryset, *, per_page=ITEMS_PER_PAGE, page_param='page'):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(page_param)
    page_obj = paginator.get_page(page_number)
    return page_obj, _build_pagination_querystring(request, exclude={page_param})


def _get_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()

    request.session.set_expiry(0)
    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key, defaults={'user': None})
    return cart


def _merge_guest_cart_into_user(session_key, user):
    if not session_key:
        return

    guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
    if not guest_cart:
        return

    user_cart, _ = Cart.objects.get_or_create(user=user)
    for item in guest_cart.items.select_related('product', 'variant').all():
        cart_item, created = CartItem.objects.get_or_create(
            cart=user_cart,
            product=item.product,
            variant=item.variant,
            defaults={'quantity': item.quantity},
        )
        if not created:
            cart_item.quantity += item.quantity
            cart_item.save()

    guest_cart.delete()


def _promotion_matches_product(promotion, product):
    if promotion.products.exists():
        return promotion.products.filter(id=product.id).exists()
    if promotion.categories.exists():
        return promotion.categories.filter(id__in=product.categories.values_list('id', flat=True)).exists()
    # If a promotion has no target products/categories, treat it as not applicable.
    return False


def _promotion_matches_cart_items(promotion, cart_items):
    if promotion.products.exists():
        return any(promotion.products.filter(id=item.product_id).exists() for item in cart_items)
    if promotion.categories.exists():
        for item in cart_items:
            if promotion.categories.filter(id__in=item.product.categories.values_list('id', flat=True)).exists():
                return True
        return False
    # If no targets are configured, do not apply automatically.
    return False


def _build_product_tiles(products):
    variant_ids = [variant.id for product in products for variant in product.variants.all()]
    reservation_totals = get_active_variant_reservation_totals(variant_ids)
    site_text_map = {
        item.key: item.text
        for item in SiteText.objects.filter(key__in=['product_badge_new_in', 'product_badge_hot_sale'])
    }

    tiles = []
    # Preload only automatic promotions (no code) to evaluate applicability in cards.
    active_promos = list(Promotion.objects.filter(is_active=True).filter(Q(code__isnull=True) | Q(code='')))
    now = timezone.now()
    for index, product in enumerate(products):
        original_price = (product.price * Decimal('1.18')).quantize(Decimal('0.01'))
        primary_category = product.categories.first().name if product.categories.exists() else 'Nuevo in'

        # Determine best applicable promotion (lowest final price)
        discounted_price = None
        best_promo = None
        for promo in active_promos:
            # quick validity check using promo's is_valid-like constraints (dates + active flag)
            if not promo.is_active or promo.is_deleted:
                continue
            if promo.start_date and now < promo.start_date:
                continue
            if promo.end_date and now > promo.end_date:
                continue

            if not _promotion_matches_product(promo, product):
                continue

            # compute discounted price
            price = Decimal(product.price)
            if promo.discount_type == 'percentage':
                discount = (price * promo.discount_value) / Decimal('100')
                if promo.max_discount_amount:
                    discount = min(discount, promo.max_discount_amount)
            else:
                discount = promo.discount_value

            final_price = (price - discount).quantize(Decimal('0.01'))
            if final_price < Decimal('0'):
                final_price = Decimal('0.00')

            if discounted_price is None or final_price < discounted_price:
                discounted_price = final_price
                best_promo = promo

        # Aggregate available sizes across variants (stock minus active reservations). Skip empty sizes.
        size_totals = {}
        for variant in product.variants.all():
            s = (variant.size or '').strip()
            if not s:
                continue
            qty = max(0, int(variant.stock or 0) - int(reservation_totals.get(variant.id, 0) or 0))
            size_totals[s] = size_totals.get(s, 0) + qty

        sizes = [
            {'size': sz, 'in_stock': (st > 0), 'stock': st}
            for sz, st in size_totals.items()
        ]

        # Build variant map grouped by color -> sizes
        variant_map = []
        for color in product.colors.prefetch_related('variants').all():
            color_sizes = []
            color_total = 0
            for v in color.variants.all():
                sz = (v.size or '').strip()
                st = max(0, int(v.stock or 0) - int(reservation_totals.get(v.id, 0) or 0))
                # include variant id so frontend can reference the exact variant
                color_sizes.append({'size': sz, 'stock': st, 'variant_id': v.id})
                color_total += st
            variant_map.append({'color_hex': color.color_hex, 'total': color_total, 'sizes': color_sizes})

        product_image = product.primary_image_url or FALLBACK_IMAGES[index % len(FALLBACK_IMAGES)]

        badge_text = site_text_map.get('product_badge_new_in', 'NUEVO IN') if index < 2 else site_text_map.get('product_badge_hot_sale', 'HOT SALE')

        tiles.append({
            'product': product,
            'image': product_image,
            'badge': badge_text,
            'primary_category': primary_category,
            'original_price': original_price,
            'discounted_price': discounted_price,
            'applied_promotion': best_promo,
            'sizes': sizes,
            'variant_map': variant_map,
            'variant_map_json': json.dumps(variant_map),
        })
    return tiles


def _default_product_color_rows():
    return [{
        'color_hex': '#d98bb0',
        'size_rows': [{'size': '', 'stock': 0}],
    }]


def _build_product_color_rows_from_product(product):
    if not product:
        return _default_product_color_rows()

    rows = []
    for color in product.colors.prefetch_related('variants').order_by('id'):
        size_rows = [
            {
                'size': variant.size or '',
                'stock': variant.stock,
            }
            for variant in color.variants.order_by('id')
        ]
        if not size_rows:
            size_rows = [{'size': '', 'stock': 0}]
        rows.append({'color_hex': color.color_hex, 'size_rows': size_rows})
    return rows or _default_product_color_rows()


def _build_product_color_rows_from_post(post_data):
    rows = []
    current_rows = []
    for key, value in post_data.items():
        match = re.match(r'^form-(\d+)-(color_hex|size|stock)$', key)
        if not match:
            continue
        index = int(match.group(1))
        field_name = match.group(2)
        while len(current_rows) <= index:
            current_rows.append({})
        current_rows[index][field_name] = value

    grouped = []
    for item in current_rows:
        color_hex = _normalize_hex_color(item.get('color_hex')) or '#d98bb0'
        size_value = (item.get('size') or '').strip()
        stock_raw = (item.get('stock') or '0').strip()
        try:
            stock_value = int(stock_raw or 0)
        except ValueError:
            stock_value = 0
        grouped.append({'color_hex': color_hex, 'size_rows': [{'size': size_value, 'stock': stock_value}]})

    if not grouped:
        return _default_product_color_rows()

    merged = []
    for row in grouped:
        if merged and merged[-1]['color_hex'] == row['color_hex']:
            merged[-1]['size_rows'].extend(row['size_rows'])
        else:
            merged.append({'color_hex': row['color_hex'], 'size_rows': list(row['size_rows'])})

    return merged


def _build_product_gallery_slots_from_product(product):
    gallery_images = list(product.gallery_images.order_by('position')) if product else []
    slots = []
    for position in range(1, 11):
        gallery_image = next((item for item in gallery_images if item.position == position), None)
        slots.append({
            'position': position,
            'field_name': f'gallery_image_{position}',
            'existing': gallery_image,
            'existing_url': getattr(gallery_image.image, 'url', '') if gallery_image and gallery_image.image else '',
        })
    return slots


def _save_product_gallery_images(product, files, post_data):
    """
    Save uploaded gallery images and handle deletion flags from the admin form.
    Expects `post_data` (request.POST) to contain optional `gallery_delete_<pos>` flags.
    """
    for position in range(1, 11):
        delete_flag = post_data.get(f'gallery_delete_{position}')
        existing_image = ProductGalleryImage.objects.filter(product=product, position=position).first()
        if delete_flag and existing_image:
            existing_image.delete()
            continue

        field_name = f'gallery_image_{position}'
        uploaded_file = files.get(field_name)
        if not uploaded_file:
            continue

        if existing_image:
            existing_image.image = uploaded_file
            existing_image.save(update_fields=['image'])
        else:
            ProductGalleryImage.objects.create(product=product, image=uploaded_file, position=position)


def _save_product_colors_and_variants(product, post_data):
    color_values = []
    for item in post_data.getlist('colors_hex'):
        normalized = _normalize_hex_color(item)
        if normalized:
            color_values.append(normalized)

    current_rows = []
    for key, value in post_data.items():
        match = re.match(r'^form-(\d+)-(color_hex|size|stock)$', key)
        if not match:
            continue
        index = int(match.group(1))
        field_name = match.group(2)
        while len(current_rows) <= index:
            current_rows.append({})
        current_rows[index][field_name] = value

    product.variants.all().delete()
    product.colors.all().delete()

    product_colors = {}
    
    # 🌟 CORRECCIÓN CLAVE: Usamos set() para eliminar duplicados de la lista automáticamente
    # y usamos get_or_create para que si el color ya se guardó, no intente crearlo de nuevo y dar error.
    for color_value in set(color_values):
        product_color, created = ProductColor.objects.get_or_create(product=product, color_hex=color_value)
        product_colors[color_value] = product_color

    for item in current_rows:
        color_hex = _normalize_hex_color(item.get('color_hex'))
        size_value = (item.get('size') or '').strip()
        stock_raw = (item.get('stock') or '').strip()

        if not color_hex:
            continue
        if not size_value and stock_raw in ('', '0'):
            continue

        product_color = product_colors.get(color_hex)
        if product_color is None:
            # 🌟 También blindamos esta parte con get_or_create
            product_color, created = ProductColor.objects.get_or_create(product=product, color_hex=color_hex)
            product_colors[color_hex] = product_color

        try:
            stock_value = int(stock_raw or 0)
        except ValueError:
            stock_value = 0

        ProductVariant.objects.create(
            product=product,
            color=product_color,
            size=size_value,
            stock=stock_value,
        )

def _resolve_product_variant(product, variant_id):
    if not variant_id:
        return None
    return product.variants.select_related('color').filter(id=variant_id).first()


def _resolve_shipping_zone_for_point(latitude, longitude):
    if latitude is None or longitude is None:
        return None
    for zone in ShippingZone.objects.filter(is_active=True):
        if zone.point_in_polygon(latitude, longitude):
            return zone
    return None


def _select_applicable_promotion(cart_items, subtotal, promo_code=None):
    promo_code = (promo_code or '').strip().upper()
    if promo_code:
        promotion = Promotion.objects.filter(code__iexact=promo_code, is_deleted=False).first()
        if promotion and promotion.is_valid():
            # Promo codes are global by design: they can apply to any cart.
            discount, total = promotion.apply_discount(subtotal, cart_items, ignore_targets=True)
            if discount > 0:
                return promotion, discount, total
        return None, Decimal('0.00'), subtotal

    best_promotion = None
    best_discount = Decimal('0.00')
    best_total = subtotal
    for promotion in Promotion.objects.filter(is_active=True, is_deleted=False).filter(Q(code__isnull=True) | Q(code='')):
        if not promotion.is_valid():
            continue
        # Only consider automatic promotions that actually apply to the current cart.
        if not _promotion_matches_cart_items(promotion, cart_items):
            continue
        discount, total = promotion.apply_discount(subtotal, cart_items)
        if discount > best_discount:
            best_promotion = promotion
            best_discount = discount
            best_total = total

    return best_promotion, best_discount, best_total


def _shipping_zone_map_payload():
    center_map = {
        'La Plata': {'lat': -34.933333333333, 'lng': -57.95},
        'Berisso': {'lat': -34.866666666667, 'lng': -57.866666666667},
        'Ensenada': {'lat': -34.85, 'lng': -57.9},
    }
    payload = []
    for zone in ShippingZone.objects.filter(is_active=True).order_by('name'):
        zone_data = ShippingZoneDetailSerializer(zone).data
        zone_data['center'] = center_map.get(zone.name)
        payload.append(zone_data)
    return payload


def _create_mercado_pago_preference(order, payment_transaction):
    access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '') or os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')
    if not access_token:
        return f'https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id={payment_transaction.external_reference}'

    payload = {
        'external_reference': payment_transaction.external_reference,
        'items': [
            {
                'title': f'BY Josephine - Pedido #{order.id}',
                'quantity': 1,
                'unit_price': float(order.grand_total),
                'currency_id': 'ARS',
            }
        ],
        'payer': {
            'name': order.customer_name,
            'phone': {'number': order.phone},
        },
        'back_urls': {
            'success': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000') + f'/pedido/{order.id}/',
            'pending': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000') + f'/pedido/{order.id}/',
            'failure': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000') + f'/pedido/{order.id}/',
        },
        'auto_return': 'approved',
        'notification_url': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000') + '/api/payments/transactions/webhook/',
    }

    req = urllib_request.Request(
        'https://api.mercadopago.com/checkout/preferences',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('init_point') or data.get('sandbox_init_point') or ''
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError):
        return f'https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id={payment_transaction.external_reference}'


def index(request):
    # Tu lógica actual que trae los productos para la home...
    products = Product.objects.prefetch_related('categories', 'colors__variants', 'variants', 'gallery_images').filter(is_deleted=False).order_by('-id')[:8]
    
    # 🌟 PASO A: AGREGÁ ESTA LÍNEA AQUÍ (Trae los lanzamientos activos)
    drops = Drop.objects.filter(is_active=True).order_by('-id')

    return render(request, 'home.html', {
        'products': products,
        'product_tiles': _build_product_tiles(products),
        # ... cualquier otra variable que ya tengas en tu contexto ...
        
        # 🌟 PASO B: SUMÁ ESTA LÍNEA AL CONTEXTO
        'drops': drops,
    })

def catalog(request):
    search_form = SiteSearchForm(request.GET or None)
    products = Product.objects.prefetch_related('categories', 'colors__variants', 'variants', 'gallery_images').order_by('-id')
    
    # 🌟 1. Atrapamos ambos parámetros
    category_id = request.GET.get('category')
    drop_id = request.GET.get('drop')

    if search_form.is_valid():
        query = (search_form.cleaned_data.get('q') or '').strip()
        if query:
            products = products.filter(
                Q(name__icontains=query) | Q(description__icontains=query) | Q(sku__icontains=query)
            ).distinct()

    if category_id and str(category_id).isdigit():
        products = products.filter(categories__id=category_id).distinct()
        
    # 🌟 2. Aplicamos el filtro del Drop si el usuario seleccionó uno
    if drop_id and str(drop_id).isdigit():
        products = products.filter(drop_id=drop_id).distinct()

    page_obj, pagination_query = _paginate_queryset(request, products)
    page_products = list(page_obj.object_list)

    return render(request, 'catalog.html', {
        'search_form': search_form,
        'category_id': category_id or '',
        'drop_id': drop_id or '', # 🌟 3. Lo pasamos al contexto para que el select mantenga la opción elegida
        'categories': Category.objects.all().order_by('name'),
        'drops': Drop.objects.filter(is_active=True).order_by('-id'), # 🌟 4. Mandamos los drops activos al HTML
        'products': page_products,
        'product_tiles': _build_product_tiles(page_products),
        'page_obj': page_obj,
        'pagination_query': pagination_query,
    })

def product_detail(request, pk):
    product = get_object_or_404(Product.objects.prefetch_related('categories', 'colors__variants', 'variants', 'gallery_images'), pk=pk)
    detail_tile = _build_product_tiles([product])[0]
    related_products = Product.objects.prefetch_related('categories', 'colors', 'gallery_images').filter(
        categories__in=product.categories.all()
    ).exclude(pk=product.pk).distinct()[:4]
    form = AddToCartForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        variant_id = form.cleaned_data.get('variant_id')
        quantity = form.cleaned_data['quantity']
        variant = _resolve_product_variant(product, variant_id)

        if variant is None:
            form.add_error(None, 'Seleccioná un color y talle válidos.')
        else:
            cart = _get_cart(request)
            available_stock = get_variant_available_stock(variant)
            
            # 🌟 CORRECCIÓN: Buscamos cuántos tiene ya en el carrito
            current_cart_qty = 0
            existing_item = CartItem.objects.filter(cart=cart, product=product, variant=variant).first()
            if existing_item:
                current_cart_qty = existing_item.quantity

            # Sumamos lo que pide + lo que ya tiene
            if available_stock < (quantity + current_cart_qty):
                if current_cart_qty > 0:
                    form.add_error(None, f'Solo quedan {available_stock} unidades (ya tenés {current_cart_qty} en el carrito).')
                else:
                    form.add_error(None, f'Solo quedan {available_stock} unidades disponibles para esta variante.')
            else:
                with transaction.atomic():
                    cart_item, created = CartItem.objects.select_for_update().get_or_create(
                        cart=cart,
                        product=product,
                        variant=variant,
                        defaults={'quantity': quantity},
                    )
                    if not created:
                        cart_item.quantity += quantity
                        cart_item.save(update_fields=['quantity'])
                messages.success(request, f'{product.name} agregado al carrito.')
                return redirect('web:cart')

    # Build gallery image list starting from the cover...
    gallery_list = []
    cover = detail_tile.get('image')
    if cover:
        gallery_list.append(cover)
    for gallery_image in product.gallery_images.order_by('position'):
        url = getattr(gallery_image.image, 'url', '')
        if not url:
            continue
        if not gallery_list or gallery_list[-1] != url:
            gallery_list.append(url)

    return render(request, 'product_detail.html', {
        'product': product,
        'cover_image': detail_tile['image'],
        'gallery_images': gallery_list,
        'original_price': detail_tile['original_price'],
        'discounted_price': detail_tile['discounted_price'],
        'applied_promotion': detail_tile['applied_promotion'],
        'related_products': related_products,
        'add_form': form,
        'detail_tile': detail_tile,
    })

def cart_view(request):
    cart = _get_cart(request)
    cart_items = list(cart.items.select_related('product', 'variant__color').prefetch_related('product__gallery_images').all())

    for item in cart_items:
        item.available_stock = get_variant_available_stock(item.variant) if item.variant else int(item.product.stock or 0)

    subtotal = cart.get_total()
    applied_promotion, discount_amount, discounted_total = _select_applicable_promotion(cart_items, subtotal)

    # 🌟 CORRECCIÓN: Calculamos el precio original y el descuento por cada ítem individual
    for item in cart_items:
        item.original_price = item.product.price
        item.discounted_price = None
        
        if applied_promotion and _promotion_matches_product(applied_promotion, item.product):
            price = Decimal(item.product.price)
            if applied_promotion.discount_type == 'percentage':
                discount = (price * applied_promotion.discount_value) / Decimal('100')
                if applied_promotion.max_discount_amount:
                    discount = min(discount, applied_promotion.max_discount_amount)
            else:
                discount = applied_promotion.discount_value
                
            final_price = (price - discount).quantize(Decimal('0.01'))
            item.discounted_price = final_price if final_price >= Decimal('0') else Decimal('0.00')

    if request.method == 'POST':
        action = request.POST.get('action')
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')

        if action == 'update' and product_id:
            form = CartLineForm(request.POST)
            if form.is_valid():
                item = get_object_or_404(
                    CartItem,
                    cart=cart,
                    product_id=product_id,
                    variant_id=variant_id or None,
                )
                quantity = form.cleaned_data['quantity']
                available_stock = get_variant_available_stock(item.variant) if item.variant else int(item.product.stock or 0)
                if quantity <= 0:
                    item.delete()
                    messages.success(request, 'Producto eliminado del carrito.')
                    return redirect('web:cart')
                else:
                    if available_stock <= 0:
                        item.delete()
                        messages.error(request, f'{item.product.name} ya no tiene stock disponible y fue quitado.')
                        return redirect('web:cart')

                    if quantity > available_stock:
                        quantity = available_stock
                        messages.warning(
                            request,
                            f'Solo quedan {available_stock} unidades disponibles de {item.product.name}. Se ajustó la cantidad.',
                        )

                    item.quantity = quantity
                    item.save()
                messages.success(request, 'Carrito actualizado.')
                return redirect('web:cart')

        if action == 'remove' and product_id:
            get_object_or_404(
                CartItem,
                cart=cart,
                product_id=product_id,
                variant_id=variant_id or None,
            ).delete()
            messages.success(request, 'Producto eliminado del carrito.')
            return redirect('web:cart')

        if action == 'clear':
            cart.items.all().delete()
            messages.success(request, 'Carrito vaciado.')
            return redirect('web:cart')

    return render(request, 'cart.html', {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'discounted_total': discounted_total,
        'applied_promotion': applied_promotion,
        'shipping_zones': ShippingZone.objects.filter(is_active=True).order_by('name'),
    })

def _create_product_reservation(request, cart_items, reservation_minutes=15):
    """
    Create or update temporary reservation for all cart items to prevent race conditions.
    Returns reservation_data dict with expiration time.
    """
    from orders.models import ProductReservation
    
    now = timezone.now()
    expires_at = now + timezone.timedelta(minutes=reservation_minutes)
    
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key or ''
    
    reservations = []
    try:
        with transaction.atomic():
            for item in cart_items:
                variant = item.variant or item.product.variants.first()
                if not variant:
                    raise ValidationError(f'{item.product.name} no tiene variante válida.')
                
                # Lock the variant to check stock
                locked = ProductVariant.objects.select_for_update().get(id=variant.id)
                available = get_variant_available_stock(
                    locked,
                    exclude_user=user,
                    exclude_session_key=session_key,
                )

                if available < item.quantity:
                    raise ValidationError(
                        f'Stock insuficiente para {item.product.name}. Solo quedan {available} unidades disponibles.'
                    )
                
                # Get or create reservation (avoid duplicates by updating existing)
                res, created = ProductReservation.objects.get_or_create(
                    variant=variant,
                    user=user,
                    session_key=session_key,
                    defaults={
                        'quantity': item.quantity,
                        'expires_at': expires_at,
                        'is_active': True,
                    }
                )
                
                # If reservation exists, update expiration time and keep quantity
                if not created:
                    res.expires_at = expires_at
                    res.is_active = True
                    res.quantity = item.quantity  # Update quantity from current cart
                    res.save()
                
                reservations.append(res)
        
        return {
            'success': True,
            'expires_at': expires_at.isoformat(),
            'reservation_count': len(reservations),
        }
    except ValidationError as exc:
        return {'success': False, 'error': _validation_error_text(exc)}


def _verify_reservations_valid(request, cart_items):
    """
    Check if all cart items still have valid reservations.
    """
    from orders.models import ProductReservation
    
    now = timezone.now()
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key or ''
    
    for item in cart_items:
        variant = item.variant or item.product.variants.first()
        if not variant:
            return False, f'{item.product.name} no tiene variante válida.'
        
        res = ProductReservation.objects.filter(
            variant=variant,
            quantity=item.quantity,
            user=user,
            session_key=session_key,
            is_active=True,
            expires_at__gt=now,
        ).first()
        
        if not res:
            return False, f'La reserva para {item.product.name} expiró. Por favor, intenta nuevamente.'
    
    return True, None


def _consume_reservations(request, cart_items):
    """
    Mark reservations as consumed and reduce stock.
    """
    from orders.models import ProductReservation
    
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key or ''
    
    try:
        with transaction.atomic():
            for item in cart_items:
                variant = item.variant or item.product.variants.first()
                if not variant:
                    raise ValidationError(f'{item.product.name} no tiene variante válida.')
                
                # Deactivate reservation and reduce stock
                res = ProductReservation.objects.select_for_update().get(
                    variant=variant,
                    quantity=item.quantity,
                    user=user,
                    session_key=session_key,
                    is_active=True,
                )
                res.is_active = False
                res.save(update_fields=['is_active'])
                
                locked_variant = ProductVariant.objects.select_for_update().get(id=variant.id)
                locked_variant.stock -= item.quantity
                locked_variant.save(update_fields=['stock'])
        
        return True, None
    except Exception as exc:
        return False, _validation_error_text(exc)


def checkout_view(request):
    """
    Two-step checkout with concurrency control:
    Step 1 (GET): Show choice - Retiro o Envío
    Step 2 (GET with step=form): Show delivery form with optional map
    Both steps use reservations to prevent race conditions
    """
    from orders.models import ProductReservation
    
    cart = _get_cart(request)
    checkout_session_key = request.session.session_key or ''
    cart_items = list(cart.items.select_related('product', 'variant__color').all())

    pending_order_id = request.session.get('_pending_checkout_order_id')
    if pending_order_id:
        pending_order = Order.objects.filter(id=pending_order_id).first()
        pending_payment = pending_order.payments.order_by('-created_at').first() if pending_order else None
        if not (pending_order and pending_payment and pending_payment.provider == PaymentTransaction.ProviderChoices.MERCADO_PAGO and pending_payment.status == PaymentTransaction.StatusChoices.PENDING):
            request.session.pop('_pending_checkout_order_id', None)
            request.session.pop('_pending_checkout_payment_ref', None)
    
    if not cart_items:
        messages.error(request, 'No hay productos en el carrito.')
        return redirect('web:cart')
    
    step = request.GET.get('step', 'delivery-choice')
    
    # STEP 1: Delivery choice (Retiro or Envío)
    if step == 'delivery-choice':
        # Try to create/verify reservations
        valid, error = _verify_reservations_valid(request, cart_items)
        
        # If no valid reservations exist, create new ones
        if not valid:
            res_data = _create_product_reservation(request, cart_items)
            if not res_data['success']:
                messages.error(request, res_data['error'])
                return redirect('web:cart')
            request.session['_checkout_reservations_active'] = True
            request.session['_checkout_expires_at'] = res_data['expires_at']
            request.session.set_expiry(int(15 * 60))  # 15 minute session
        else:
            # Reservations still valid, refresh the session expiry
            request.session.set_expiry(int(15 * 60))
        
        return redirect(f"{reverse('web:checkout')}?step=form&method=shipping")
    
    # STEP 2: Delivery form (choice already made)
    elif step == 'form':
        # Verify reservations still valid
        valid, error = _verify_reservations_valid(request, cart_items)
        if not valid:
            messages.warning(request, 'El tiempo de compra ha expirado. Por favor, intenta de nuevo. Tu carrito se mantiene intacto.')
            # Clean up session flags to allow retry
            request.session['_checkout_reservations_active'] = False
            ProductReservation.objects.filter(
                user=request.user,
                session_key=request.session.session_key,
                is_active=True,
            ).delete()
            return redirect('web:checkout')
        
        delivery_method = 'shipping'
        form = CheckoutForm(request.POST or None)
        subtotal = Decimal('0.00')
        for item in cart_items:
            subtotal += item.product.price * item.quantity

        preview_promo_code = (request.POST.get('promo_code') or '').strip() if request.method == 'POST' else ''
        applied_promotion, discount_amount, discounted_total = _select_applicable_promotion(
            cart_items,
            subtotal,
            preview_promo_code,
        )
        
        if request.method == 'POST' and form.is_valid():
            # Final validation and order creation
            valid, error = _verify_reservations_valid(request, cart_items)
            if not valid:
                messages.warning(request, 'El tiempo de compra ha expirado. Por favor, intenta de nuevo. Tu carrito se mantiene intacto.')
                request.session['_checkout_reservations_active'] = False
                ProductReservation.objects.filter(
                    user=request.user,
                    session_key=request.session.session_key,
                    is_active=True,
                ).delete()
                return redirect('web:checkout')
            
            promo_code = form.cleaned_data.get('promo_code') or ''
            promotion, discount, discounted_subtotal = _select_applicable_promotion(
                cart_items,
                subtotal,
                promo_code,
            )
            
            delivery_method = form.cleaned_data['delivery_method']
            province = form.cleaned_data.get('province', '')
            city = form.cleaned_data.get('city', '')
            shipping_zone = None
            shipping_cost = Decimal('0.00')
            grand_total = discounted_subtotal
            
            owner_user = request.user if request.user.is_authenticated else None

            try:
                with transaction.atomic():
                    # Create order
                    order = Order.objects.create(
                        user=owner_user,
                        customer_name=form.cleaned_data['customer_name'],
                        customer_email=form.cleaned_data['customer_email'],
                        phone=form.cleaned_data['phone'],
                        delivery_method=delivery_method,
                        delivery_address=form.cleaned_data.get('address', ''),
                        delivery_latitude=form.cleaned_data.get('latitude'),
                        delivery_longitude=form.cleaned_data.get('longitude'),
                        shipping_zone=shipping_zone,
                        pickup_point=None,
                        promotion=promotion,
                        promo_code=promo_code,
                        discount_amount=discount,
                        total=discounted_subtotal,
                        shipping_cost=shipping_cost,
                        status=Order.StatusChoices.PENDING,
                        payment_status=Order.PaymentStatusChoices.PENDING,
                        notes=(
                            f'Checkout frontend. Método: {delivery_method}. '
                            f'Provincia: {province}. Ciudad: {city}. '
                            f'Envío coordinado con vendedor. '
                            f'Promo: {promo_code or (promotion.code if promotion else "")}. '
                        ),
                    )
                    
                    # Create order items
                    for item in cart_items:
                        variant = item.variant or item.product.variants.first()
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            variant=variant,
                            variant_size=(variant.size if variant and variant.size else ''),
                            quantity=item.quantity,
                            unit_price=item.product.price,
                        )
                    
                    # Create payment transaction
                    payment_method = form.cleaned_data['payment_method']
                    payment = PaymentTransaction.objects.create(
                        user=owner_user,
                        order=order,
                        provider=(PaymentTransaction.ProviderChoices.MERCADO_PAGO
                                if payment_method == 'mercado_pago'
                                else PaymentTransaction.ProviderChoices.CASH),
                        payment_method=payment_method,
                        amount=grand_total,
                        status=PaymentTransaction.StatusChoices.PENDING,
                        external_reference=f'JOSEPHINE-{order.id}-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                        provider_payload={
                            'source': 'frontend_checkout',
                            'subtotal': str(subtotal),
                            'discount_amount': str(discount),
                            'shipping_cost': str(shipping_cost),
                            'grand_total': str(grand_total),
                            'shipping_zone': '',
                            'pickup_point': '',
                            'province': province,
                            'city': city,
                            'delivery_method': delivery_method,
                            'session_key': checkout_session_key,
                            'user_id': owner_user.id if owner_user else None,
                        },
                    )
                    
                    # Handle Mercado Pago payment
                    if payment_method == 'mercado_pago':
                        checkout_url = _create_mercado_pago_preference(order, payment)
                        payment.checkout_url = checkout_url
                        payment.save(update_fields=['checkout_url', 'updated_at'])

                        request.session['_pending_checkout_order_id'] = order.id
                        request.session['_pending_checkout_payment_ref'] = payment.external_reference
                        # Consume reservations immediately and decrement real stock so
                        # the order reflects reserved inventory even while pending payment.
                        success, error = _consume_reservations(request, cart_items)
                        if not success:
                            raise ValidationError(f'Error al procesar reservas: {error}')
                        cart.items.all().delete()
                        request.session['_checkout_reservations_active'] = False
                        request.session['_checkout_expires_at'] = None
                        if owner_user is None:
                            guest_orders = request.session.get('guest_orders', [])
                            if order.id not in guest_orders:
                                guest_orders.append(order.id)
                                request.session['guest_orders'] = guest_orders
                    else:
                        # Cash: consume reservations immediately and clear the cart
                        success, error = _consume_reservations(request, cart_items)
                        if not success:
                            raise ValidationError(f'Error al procesar reservas: {error}')
                        cart.items.all().delete()
                        request.session['_checkout_reservations_active'] = False
                        request.session['_checkout_expires_at'] = None
                        if owner_user is None:
                            guest_orders = request.session.get('guest_orders', [])
                            if order.id not in guest_orders:
                                guest_orders.append(order.id)
                                request.session['guest_orders'] = guest_orders
                
                if payment_method == 'mercado_pago' and payment.checkout_url:
                    return redirect(payment.checkout_url)
                messages.success(request, 'Pedido creado correctamente.')
                return redirect('web:order_success', order_id=order.id)
            
            except ValidationError as exc:
                messages.error(request, _validation_error_text(exc))
                return redirect(f"{reverse('web:checkout')}?step=form&method={delivery_method}")
        
        expires_at = request.session.get('_checkout_expires_at')
        payment_total = discounted_total
        # Build an itemized summary for display (unit, qty, line total)
        cart_summary_items = []
        for ci in cart_items:
            unit_price = getattr(ci.product, 'price', 0) or 0
            quantity = getattr(ci, 'quantity', 1) or 1
            line_total = unit_price * quantity
            variant = getattr(ci, 'variant', None)
            color = getattr(getattr(variant, 'color', None), 'display_name', '') if variant else ''
            color_hex = getattr(getattr(variant, 'color', None), 'color_hex', '') if variant else ''
            cart_summary_items.append({
                'name': ci.product.name,
                'variant': variant and getattr(variant, 'size', '') or '',
                'color': color,
                'color_hex': color_hex,
                'unit_price': unit_price,
                'quantity': quantity,
                'line_total': line_total,
            })
        return render(request, 'checkout.html', {
            'cart': cart,
            'cart_items': cart_items,
            'total': subtotal,
            'cart_summary_items': cart_summary_items,
            'discount_amount': discount_amount,
            'discounted_total': discounted_total,
            'applied_promotion': applied_promotion,
            'payment_total': payment_total,
            'step': 'form',
            'delivery_method': delivery_method,
            'expires_at': expires_at,
            'shipping_zones_map': _shipping_zone_map_payload(),
            'form': form,
        })
    
    # Default: redirect to delivery choice step
    return redirect(reverse('web:checkout'))


def order_success(request, order_id):
    order = get_object_or_404(Order.objects.select_related('user'), id=order_id)
    if order.user and (not request.user.is_authenticated or order.user_id != request.user.id):
        return redirect('web:login')
    if order.user is None:
        guest_orders = request.session.get('guest_orders', [])
        if order.id not in guest_orders:
            return redirect('web:index')
    payment = order.payments.order_by('-created_at').first()

    pending_order_id = request.session.get('_pending_checkout_order_id')
    if pending_order_id == order.id and payment and payment.status != PaymentTransaction.StatusChoices.PENDING:
        request.session.pop('_pending_checkout_order_id', None)
        request.session.pop('_pending_checkout_payment_ref', None)
        request.session.pop('_checkout_reservations_active', None)
        request.session.pop('_checkout_expires_at', None)

    return render(request, 'order_success.html', {
        'order': order,
        'payment': payment,
    })


def order_lookup(request):
    form = OrderLookupForm(request.GET or None)
    orders = []
    searched_email = ''
    page_obj = None
    pagination_query = ''

    if request.GET and form.is_valid():
        searched_email = form.cleaned_data['email'].strip().lower()
        orders_queryset = (
            Order.objects.filter(
                Q(customer_email__iexact=searched_email) | Q(user__email__iexact=searched_email)
            )
            .select_related('user', 'shipping_zone', 'pickup_point')
            .prefetch_related('orderitem_set__product', 'orderitem_set__variant', 'payments')
            .order_by('-created_at')
        )
        page_obj, pagination_query = _paginate_queryset(request, orders_queryset)
        orders = list(page_obj.object_list)

    return render(request, 'order_lookup.html', {
        'form': form,
        'orders': orders,
        'searched_email': searched_email,
        'page_obj': page_obj,
        'pagination_query': pagination_query,
    })


def _order_status_meta(status_value):
    labels = {
        Order.StatusChoices.PENDING: {'title': 'Pendiente', 'subtitle': 'Esperando confirmación de pago'},
        Order.StatusChoices.CONFIRMED: {'title': 'Confirmado', 'subtitle': 'Pago aprobado, listo para preparar'},
        Order.StatusChoices.REJECTED: {'title': 'Rechazada', 'subtitle': 'Pedido rechazado por administración'},
        Order.StatusChoices.PROCESSING: {'title': 'Empaquetando', 'subtitle': 'Preparando el pedido'},
        Order.StatusChoices.SHIPPED: {'title': 'En Camino', 'subtitle': 'Pedido enviado o en reparto'},
        Order.StatusChoices.DELIVERED: {'title': 'Finalizado', 'subtitle': 'Pedido completado'},
        Order.StatusChoices.CANCELLED: {'title': 'Cancelado', 'subtitle': 'Pedido cancelado'},
    }
    return labels.get(status_value, {'title': status_value.title(), 'subtitle': ''})


def _get_order_transition_buttons(order):
    if order.status == Order.StatusChoices.REJECTED:
        return []

    buttons = []

    if order.status in ORDER_FLOW and order.status != Order.StatusChoices.PENDING:
        index = ORDER_FLOW.index(order.status)
        if index > 1:
            buttons.append({
                'label': 'Volver',
                'target': ORDER_FLOW[index - 1],
                'direction': 'back',
            })
        if index < len(ORDER_FLOW) - 1:
            buttons.append({
                'label': 'Siguiente',
                'target': ORDER_FLOW[index + 1],
                'direction': 'next',
            })

    if order.status in REJECTABLE_ORDER_STATUSES:
        buttons.append({
            'label': 'Rechazar',
            'target': Order.StatusChoices.REJECTED,
            'direction': 'reject',
        })

    return buttons


@staff_member_required
def admin_orders(request):
    selected_status = request.GET.get('status', Order.StatusChoices.CONFIRMED)
    selected_order_number = (request.GET.get('order_number') or '').strip()
    if selected_status not in ORDER_ADMIN_STATUSES:
        selected_status = ORDER_FLOW[0]
    selected_page = request.GET.get('page')

    if request.method == 'POST':
        selected_status = request.POST.get('status', selected_status)
        selected_order_number = (request.POST.get('order_number') or selected_order_number).strip()
        selected_page = request.POST.get('page', selected_page)
        if selected_status not in ORDER_ADMIN_STATUSES:
            selected_status = ORDER_FLOW[0]

        with transaction.atomic():
            order_id = request.POST.get('order_id')
            target_status = request.POST.get('target_status')
            order = get_object_or_404(Order.objects.select_for_update(), id=order_id)

            redirect_target = f"{reverse('web:admin_orders')}?status={selected_status}"
            if selected_order_number:
                redirect_target += f"&order_number={selected_order_number}"
            if selected_page:
                redirect_target += f"&page={selected_page}"

            if target_status == Order.StatusChoices.REJECTED:
                if order.status not in REJECTABLE_ORDER_STATUSES:
                    messages.warning(request, 'Solo las órdenes pendientes o confirmadas pueden rechazarse.')
                    return redirect(redirect_target)

                restored_items, restored_reservations = restore_order_stock(order)
                order.status = Order.StatusChoices.REJECTED
                if order.payment_status == Order.PaymentStatusChoices.PENDING:
                    order.payment_status = Order.PaymentStatusChoices.FAILED
                order.save(update_fields=['status', 'payment_status', 'updated_at'])
                messages.success(
                    request,
                    f'La orden #{order.id} fue rechazada. Stock restaurado en {restored_items} item(s) y {restored_reservations} reserva(s) desactivada(s).',
                )
                return redirect(redirect_target)

            if order.status == Order.StatusChoices.PENDING:
                messages.warning(request, 'Las órdenes pendientes solo pueden rechazarse desde este panel.')
                return redirect(redirect_target)

            if order.status == Order.StatusChoices.CONFIRMED and target_status == Order.StatusChoices.PENDING:
                messages.warning(request, 'No se puede volver de Confirmado a Pendiente.')
                return redirect(redirect_target)

            current_index = ORDER_FLOW.index(order.status) if order.status in ORDER_FLOW else None
            target_index = ORDER_FLOW.index(target_status) if target_status in ORDER_FLOW else None

            if current_index is None or target_index is None:
                messages.error(request, 'Estado no válido.')
                return redirect(redirect_target)

            if abs(target_index - current_index) != 1:
                messages.warning(request, 'Solo podés mover la orden al estado anterior o siguiente.')
                return redirect(redirect_target)

            order.status = target_status
            order.save(update_fields=['status', 'updated_at'])
            messages.success(request, f'La orden #{order.id} pasó a {order.get_status_display()}.')
            return redirect(redirect_target)

    base_orders_queryset = Order.objects.select_related('user').prefetch_related('orderitem_set__product', 'orderitem_set__variant').filter(is_deleted=False)
    if selected_order_number:
        if selected_order_number.isdigit():
            base_orders_queryset = base_orders_queryset.filter(id=int(selected_order_number))
        else:
            base_orders_queryset = base_orders_queryset.none()

    status_sections = []
    for status_value in ORDER_ADMIN_STATUSES:
        orders = list(
            base_orders_queryset
            .filter(status=status_value)
            .order_by('-created_at')
        )
        status_sections.append({
            'status': status_value,
            'meta': _order_status_meta(status_value),
            'orders': [
                {
                    'order': order,
                    'transition_buttons': _get_order_transition_buttons(order),
                }
                for order in orders
            ],
            'count': len(orders),
        })

    selected_section = next(
        (section for section in status_sections if section['status'] == selected_status),
        status_sections[0] if status_sections else None,
    )

    selected_orders_queryset = base_orders_queryset.filter(status=selected_status).order_by('-created_at')
    page_obj, pagination_query = _paginate_queryset(request, selected_orders_queryset)
    selected_orders = list(page_obj.object_list)

    if selected_section:
        selected_section = {
            **selected_section,
            'orders': [
                {
                    'order': order,
                    'transition_buttons': _get_order_transition_buttons(order),
                }
                for order in selected_orders
            ],
            'page_obj': page_obj,
            'count': selected_orders_queryset.count(),
        }

    return render(request, 'admin/orders_board.html', {
        'status_sections': status_sections,
        'selected_status': selected_status,
        'order_number_query': selected_order_number,
        'selected_section': selected_section,
        'status_filters': [
            {
                'value': status_value,
                'meta': _order_status_meta(status_value),
                'count': next((section['count'] for section in status_sections if section['status'] == status_value), 0),
            }
            for status_value in ORDER_ADMIN_STATUSES
        ],
        'page_obj': page_obj,
        'pagination_query': pagination_query,
    })


@staff_member_required
def admin_panel(request):
    return render(request, 'admin/panel.html')


@staff_member_required
def admin_site_texts(request):
    # Only allow editing of the configured keys; do not allow creating or deleting
    allowed_keys = [
        'marquee_text',
        'hero_eyebrow',
        'hero_headline',
        'hero_badge_1',
        'hero_badge_2',
        'product_badge_new_in',
        'product_badge_hot_sale',
        'footer_help_envois',
        'footer_help_talles',
    ]
    # Formset to edit existing SiteText entries (cannot change the key, no delete)
    SiteTextEditFormSet = modelformset_factory(SiteText, fields=('text', 'description'), extra=0, can_delete=False)

    class SiteTextCreateForm(forms.ModelForm):
        class Meta:
            model = SiteText
            fields = ('key', 'text', 'description')

    # Ensure we only show the allowed keys and keep order
    edit_qs = SiteText.objects.filter(key__in=allowed_keys).order_by('key')
    if request.method == 'POST':
        edit_formset = SiteTextEditFormSet(request.POST, queryset=edit_qs, prefix='edit')
        create_form = SiteTextCreateForm(request.POST, prefix='new')

        if 'save_edit' in request.POST and edit_formset.is_valid():
            edit_formset.save()
            messages.success(request, 'Textos del sitio actualizados.')
            return redirect('web:admin_site_texts')
        # creation is disabled in this view by design
    else:
        edit_formset = SiteTextEditFormSet(queryset=edit_qs, prefix='edit')
        create_form = None

    return render(request, 'admin/site_texts.html', {
        'edit_formset': edit_formset,
    })


@staff_member_required
def admin_products_list(request):
    query = (request.GET.get('q') or '').strip()
    category_id = request.GET.get('category') or ''
    status = request.GET.get('status') or 'all'

    products = Product.all_objects.prefetch_related('categories', 'colors').order_by('-id')
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(sku__icontains=query) | Q(description__icontains=query)
        ).distinct()
    if category_id.isdigit():
        products = products.filter(categories__id=category_id).distinct()
    if status == 'active':
        products = products.filter(is_deleted=False)
    elif status == 'deleted':
        products = products.filter(is_deleted=True)

    return render(request, 'admin/product_list.html', {
        'products': products,
        'categories': Category.objects.order_by('name'),
        'query': query,
        'category_id': category_id,
        'status': status,
    })


def _admin_product_form_context(request, product=None, saved=False):
    form = ProductAdminForm(request.POST or None, instance=product)
    if request.method == 'POST':
        color_rows = _build_product_color_rows_from_post(request.POST)
    else:
        color_rows = _build_product_color_rows_from_product(product)
    gallery_slots = _build_product_gallery_slots_from_product(product)

    promotions = Promotion.objects.filter(is_deleted=False).order_by('-start_date', '-id')
    selected_promotion = None
    if product is not None:
        selected_promotion = Promotion.all_objects.filter(products=product, is_deleted=False).order_by('-start_date', '-id').first()

    return {
        'form': form,
        'color_rows': color_rows,
        'gallery_slot_1': {'field': form['gallery_image_1'], 'existing_url': gallery_slots[0]['existing_url']},
        'gallery_slot_2': {'field': form['gallery_image_2'], 'existing_url': gallery_slots[1]['existing_url']},
        'gallery_slot_3': {'field': form['gallery_image_3'], 'existing_url': gallery_slots[2]['existing_url']},
        'gallery_slot_4': {'field': form['gallery_image_4'], 'existing_url': gallery_slots[3]['existing_url']},
        'gallery_slot_5': {'field': form['gallery_image_5'], 'existing_url': gallery_slots[4]['existing_url']},
        'gallery_slot_6': {'field': form['gallery_image_6'], 'existing_url': gallery_slots[5]['existing_url']},
        'gallery_slot_7': {'field': form['gallery_image_7'], 'existing_url': gallery_slots[6]['existing_url']},
        'gallery_slot_8': {'field': form['gallery_image_8'], 'existing_url': gallery_slots[7]['existing_url']},
        'gallery_slot_9': {'field': form['gallery_image_9'], 'existing_url': gallery_slots[8]['existing_url']},
        'gallery_slot_10': {'field': form['gallery_image_10'], 'existing_url': gallery_slots[9]['existing_url']},
        'promotions': promotions,
        'selected_promotion_id': selected_promotion.id if selected_promotion else '',
        'saved': saved,
        'edit_mode': product is not None,
        'product': product,
    }


@staff_member_required
def admin_product_new(request):
    saved = False
    form = ProductAdminForm(request.POST or None, request.FILES or None)
    VariantFormSet = inlineformset_factory(Product, ProductVariant, form=ProductVariantForm, extra=2, can_delete=True)
    formset = VariantFormSet(request.POST or None)
    selected_category_ids = request.POST.getlist('categories') if request.method == 'POST' else []

    # 1. ESTA ES LA CORRECCIÓN CLAVE: Recuperamos colores y talles bien arriba.
    # Así, si hay un error, la página recarga pero mantiene todo lo que escribiste.
    if request.method == 'POST':
        color_rows = _build_product_color_rows_from_post(request.POST)
    else:
        color_rows = _default_product_color_rows()

    if request.method == 'POST' and form.is_valid():
        promotion_id = request.POST.get('promotion') or None

        # Additional validations
        selected_categories = request.POST.getlist('categories')
        
        # 2. CORRECCIÓN DEL STOCK 0: Cambiamos > 0 por >= 0
        has_valid_variant = any(
            any((sr.get('size') or '').strip() and int(sr.get('stock') or 0) >= 0 for sr in row.get('size_rows', []))
            for row in color_rows
        )
        name_val = form.cleaned_data.get('name')
        price_val = form.cleaned_data.get('price')

        if not selected_categories:
            form.add_error('categories', 'Seleccioná al menos una categoría.')
        if not name_val:
            form.add_error('name', 'El nombre es obligatorio.')
        if price_val is None:
            form.add_error('price', 'El precio es obligatorio.')
        if not has_valid_variant:
            form.add_error(None, 'Debés crear al menos un color con talle (el stock puede ser 0).')

        if form.errors:
            messages.error(request, 'Corrige los errores antes de guardar el producto.')
        else:
            with transaction.atomic():
                product = form.save(commit=False)
                product.is_deleted = False
                product.save()
                form.save_m2m()
                _save_product_gallery_images(product, request.FILES, request.POST)
                _save_product_colors_and_variants(product, request.POST)

                if promotion_id:
                    promotion = Promotion.all_objects.filter(id=promotion_id, is_deleted=False).first()
                    if promotion:
                        promotion.products.add(product)

            messages.success(request, f'Producto {product.name} creado correctamente.')
            saved = True
            form = ProductAdminForm(instance=product)
            color_rows = _build_product_color_rows_from_product(product)
            
    elif request.method == 'POST':
        messages.error(request, 'Completá nombre y precio válidos.')

    return render(request, 'admin/product_new.html', {
        'categories': Category.objects.order_by('name'),
        'promotions': Promotion.objects.filter(is_deleted=False).order_by('-start_date', '-id'),
        'selected_promotion_id': '',
        'gallery_slot_1': {'field': form['gallery_image_1'], 'existing_url': ''},
        'gallery_slot_2': {'field': form['gallery_image_2'], 'existing_url': ''},
        'gallery_slot_3': {'field': form['gallery_image_3'], 'existing_url': ''},
        'gallery_slot_4': {'field': form['gallery_image_4'], 'existing_url': ''},
        'gallery_slot_5': {'field': form['gallery_image_5'], 'existing_url': ''},
        'gallery_slot_6': {'field': form['gallery_image_6'], 'existing_url': ''},
        'gallery_slot_7': {'field': form['gallery_image_7'], 'existing_url': ''},
        'gallery_slot_8': {'field': form['gallery_image_8'], 'existing_url': ''},
        'gallery_slot_9': {'field': form['gallery_image_9'], 'existing_url': ''},
        'gallery_slot_10': {'field': form['gallery_image_10'], 'existing_url': ''},
        'form': form,
        'formset': formset,
        'color_rows': color_rows,
        'selected_category_ids': [str(item) for item in selected_category_ids],
        'saved': saved,
        'edit_mode': False,
        'product': None,
    })


@staff_member_required
def admin_product_edit(request, pk):
    product = get_object_or_404(Product.all_objects.prefetch_related('categories', 'colors__variants'), pk=pk)
    saved = False
    form = ProductAdminForm(request.POST or None, request.FILES or None, instance=product)
    VariantFormSet = inlineformset_factory(Product, ProductVariant, form=ProductVariantForm, extra=2, can_delete=True)
    formset = VariantFormSet(request.POST or None, instance=product)
    selected_category_ids = request.POST.getlist('categories') if request.method == 'POST' else [str(item) for item in product.categories.values_list('id', flat=True)]

    # 1. Inicializamos color_rows acá también
    if request.method == 'POST':
        color_rows = _build_product_color_rows_from_post(request.POST)
    else:
        color_rows = _build_product_color_rows_from_product(product)

    if request.method == 'POST' and form.is_valid():
        promotion_id = request.POST.get('promotion') or None

        selected_categories = request.POST.getlist('categories')
        has_valid_variant = any(
            any((sr.get('size') or '').strip() and int(sr.get('stock') or 0) >= 0 for sr in row.get('size_rows', []))
            for row in color_rows
        )
        name_val = form.cleaned_data.get('name')
        price_val = form.cleaned_data.get('price')

        if not selected_categories:
            form.add_error('categories', 'Seleccioná al menos una categoría.')
        if not name_val:
            form.add_error('name', 'El nombre es obligatorio.')
        if price_val is None:
            form.add_error('price', 'El precio es obligatorio.')
        if not has_valid_variant:
            form.add_error(None, 'Debés crear al menos un color con talle y stock.')

        if form.errors:
            messages.error(request, 'Corrige los errores antes de guardar el producto.')
        else:
            with transaction.atomic():
                product = form.save(commit=False)
                product.is_deleted = False
                product.save()
                form.save_m2m()
                _save_product_gallery_images(product, request.FILES, request.POST)
                _save_product_colors_and_variants(product, request.POST)

                current_promotions = list(Promotion.all_objects.filter(products=product, is_deleted=False))
                if promotion_id:
                    promotion = Promotion.all_objects.filter(id=promotion_id, is_deleted=False).first()
                    if promotion:
                        for current_promotion in current_promotions:
                            if current_promotion.id != promotion.id:
                                current_promotion.products.remove(product)
                        promotion.products.add(product)
                else:
                    for current_promotion in current_promotions:
                        current_promotion.products.remove(product)

            messages.success(request, f'Producto {product.name} actualizado correctamente.')
            saved = True
            color_rows = _build_product_color_rows_from_product(product)
            
    elif request.method == 'POST':
        messages.error(request, 'Completá nombre y precio válidos.')

    return render(request, 'admin/product_new.html', {
        'categories': Category.objects.order_by('name'),
        'promotions': Promotion.objects.filter(is_deleted=False).order_by('-start_date', '-id'),
        'selected_promotion_id': (
            Promotion.all_objects.filter(products=product, is_deleted=False)
            .order_by('-start_date', '-id')
            .values_list('id', flat=True)
            .first() or ''
        ),
        'gallery_slot_1': {'field': form['gallery_image_1'], 'existing_url': _build_product_gallery_slots_from_product(product)[0]['existing_url']},
        'gallery_slot_2': {'field': form['gallery_image_2'], 'existing_url': _build_product_gallery_slots_from_product(product)[1]['existing_url']},
        'gallery_slot_3': {'field': form['gallery_image_3'], 'existing_url': _build_product_gallery_slots_from_product(product)[2]['existing_url']},
        'gallery_slot_4': {'field': form['gallery_image_4'], 'existing_url': _build_product_gallery_slots_from_product(product)[3]['existing_url']},
        'gallery_slot_5': {'field': form['gallery_image_5'], 'existing_url': _build_product_gallery_slots_from_product(product)[4]['existing_url']},
        'gallery_slot_6': {'field': form['gallery_image_6'], 'existing_url': _build_product_gallery_slots_from_product(product)[5]['existing_url']},
        'gallery_slot_7': {'field': form['gallery_image_7'], 'existing_url': _build_product_gallery_slots_from_product(product)[6]['existing_url']},
        'gallery_slot_8': {'field': form['gallery_image_8'], 'existing_url': _build_product_gallery_slots_from_product(product)[7]['existing_url']},
        'gallery_slot_9': {'field': form['gallery_image_9'], 'existing_url': _build_product_gallery_slots_from_product(product)[8]['existing_url']},
        'gallery_slot_10': {'field': form['gallery_image_10'], 'existing_url': _build_product_gallery_slots_from_product(product)[9]['existing_url']},
        'form': form,
        'formset': formset,
        'color_rows': color_rows,
        'selected_category_ids': [str(item) for item in selected_category_ids],
        'saved': saved,
        'edit_mode': True,
        'product': product,
    })

@staff_member_required
def admin_product_delete(request, pk):
    product = get_object_or_404(Product.all_objects, pk=pk)
    if request.method == 'POST':
        product.is_deleted = True
        product.save(update_fields=['is_deleted'])
        messages.success(request, f'Producto {product.name} eliminado lógicamente.')
    return redirect('web:admin_products_list')


@staff_member_required
def admin_categories_list(request):
    query = (request.GET.get('q') or '').strip()
    status = request.GET.get('status') or 'all'

    categories = Category.all_objects.order_by('name')
    if query:
        categories = categories.filter(name__icontains=query)
    if status == 'active':
        categories = categories.filter(is_deleted=False)
    elif status == 'deleted':
        categories = categories.filter(is_deleted=True)

    return render(request, 'admin/category_list.html', {
        'categories': categories,
        'query': query,
        'status': status,
    })


def _category_form_context(request, category=None, saved=False):
    return {
        'form': CategoryAdminForm(request.POST or None, instance=category),
        'saved': saved,
        'edit_mode': category is not None,
        'category': category,
    }


@staff_member_required
def admin_category_new(request):
    saved = False
    form = CategoryAdminForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        category = form.save(commit=False)
        category.is_deleted = False
        category.save()
        messages.success(request, f'Categoría {category.name} creada correctamente.')
        saved = True
        form = CategoryAdminForm(instance=category)
    elif request.method == 'POST':
        messages.error(request, 'Completá el nombre de la categoría.')

    return render(request, 'admin/category_new.html', {
        'form': form,
        'saved': saved,
        'edit_mode': False,
    })


@staff_member_required
def admin_category_edit(request, pk):
    category = get_object_or_404(Category.all_objects, pk=pk)
    saved = False
    form = CategoryAdminForm(request.POST or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        category = form.save(commit=False)
        category.is_deleted = False
        category.save()
        messages.success(request, f'Categoría {category.name} actualizada correctamente.')
        saved = True
    elif request.method == 'POST':
        messages.error(request, 'Completá el nombre de la categoría.')

    return render(request, 'admin/category_new.html', {
        'form': form,
        'saved': saved,
        'edit_mode': True,
        'category': category,
    })


@staff_member_required
def admin_category_delete(request, pk):
    category = get_object_or_404(Category.all_objects, pk=pk)
    if request.method == 'POST':
        has_active_products = Product.all_objects.filter(is_deleted=False, categories=category).exists()
        if has_active_products:
            messages.error(request, 'No podés eliminar la categoría mientras tenga productos activos asociados.')
        else:
            category.is_deleted = True
            category.save(update_fields=['is_deleted'])
            messages.success(request, f'Categoría {category.name} eliminada lógicamente.')
    return redirect('web:admin_categories_list')


@staff_member_required
def admin_promotions_list(request):
    query = (request.GET.get('q') or '').strip()
    status = request.GET.get('status') or 'all'

    promotions = Promotion.all_objects.order_by('-start_date', '-id')
    if query:
        promotions = promotions.filter(name__icontains=query)
    if status == 'active':
        promotions = promotions.filter(is_deleted=False, is_active=True)
    elif status == 'deleted':
        promotions = promotions.filter(is_deleted=True)

    return render(request, 'admin/promotion_list.html', {
        'promotions': promotions,
        'query': query,
        'status': status,
    })


@staff_member_required
def admin_promotion_new(request):
    form = PromotionAdminForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        promotion = form.save(commit=False)
        promotion.is_deleted = False
        promotion.save()
        form.save_m2m()
        messages.success(request, f'Promoción {promotion.name} creada correctamente.')
        return redirect('web:admin_promotions_list')
    return render(request, 'admin/promotion_new.html', {
        'form': form,
        'edit_mode': False,
    })


@staff_member_required
def admin_promotion_edit(request, pk):
    promotion = get_object_or_404(Promotion.all_objects, pk=pk)
    form = PromotionAdminForm(request.POST or None, instance=promotion)
    if request.method == 'POST' and form.is_valid():
        promotion = form.save(commit=False)
        promotion.is_deleted = False
        promotion.save()
        form.save_m2m()
        messages.success(request, f'Promoción {promotion.name} actualizada correctamente.')
        return redirect('web:admin_promotions_list')
    return render(request, 'admin/promotion_new.html', {
        'form': form,
        'edit_mode': True,
        'promotion': promotion,
    })


@staff_member_required
def admin_promotion_delete(request, pk):
    promotion = get_object_or_404(Promotion.all_objects, pk=pk)
    if request.method == 'POST':
        promotion.is_deleted = True
        promotion.is_active = False
        promotion.save(update_fields=['is_deleted', 'is_active'])
        messages.success(request, f'Promoción {promotion.name} eliminada lógicamente.')
    return redirect('web:admin_promotions_list')


def login_view(request):
    form = FrontendLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        guest_session_key = request.session.session_key
        if request.POST.get('remember'):
            request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            request.session.set_expiry(0)
        user = form.get_user()
        _merge_guest_cart_into_user(guest_session_key, user)
        auth_login(request, user, backend=AUTH_BACKEND)
        return redirect(request.GET.get('next') or reverse('web:index'))
    return render(request, 'auth/login.html', {'form': form, 'hide_site_chrome': True})


def register_view(request):
    form = FrontendRegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        guest_session_key = request.session.session_key
        user = form.save()
        _merge_guest_cart_into_user(guest_session_key, user)
        auth_login(request, user, backend=AUTH_BACKEND)
        return redirect('web:index')
    return render(request, 'auth/register.html', {'form': form, 'hide_site_chrome': True})


@login_required
def logout_view(request):
    auth_logout(request)
    return redirect('web:index')


def password_reset_request_view(request):
    form = PasswordResetRequestForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        user = User.objects.filter(email__iexact=email).first()

        if not user:
            form.add_error('email', 'Usuario no encontrado.')
        else:
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_path = reverse('web:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
            reset_url = request.build_absolute_uri(reset_path)

            subject = 'Recuperar contraseña - BY Josephine'
            message = (
                f"Hola {user.first_name or user.email},\n\n"
                f"Recibimos una solicitud para restablecer tu contraseña.\n"
                f"Ingresá al siguiente enlace para crear una nueva contraseña:\n\n"
                f"{reset_url}\n\n"
                f"Si no pediste este cambio, podés ignorar este correo."
            )
            send_mail(
                subject,
                message,
                settings.EMAIL_FROM,
                [email],
                fail_silently=False,
            )
            messages.success(request, 'Te enviamos un email para recuperar tu contraseña.')
            return redirect('web:login')

    return render(request, 'auth/password_reset_request.html', {
        'form': form,
        'hide_site_chrome': True,
    })


def password_reset_confirm_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    token_is_valid = bool(user and default_token_generator.check_token(user, token))
    form = PasswordResetConfirmForm(request.POST or None, user=user)

    if request.method == 'POST':
        if not token_is_valid:
            form.add_error(None, 'El enlace de recuperación no es válido o expiró. Pedí uno nuevo.')
        elif form.is_valid():
            user.set_password(form.cleaned_data['new_password'])
            user.save(update_fields=['password'])
            messages.success(request, 'Tu contraseña fue actualizada. Ya podés iniciar sesión.')
            return redirect('web:login')

    return render(request, 'auth/password_reset_confirm.html', {
        'form': form,
        'hide_site_chrome': True,
        'token_is_valid': token_is_valid,
    })
    
def admin_drops_list(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', 'all')
    drops = Drop.objects.all().order_by('-id')

    if query:
        drops = drops.filter(name__icontains=query)

    # 🌟 FILTRAMOS POR IS_ACTIVE
    if status_filter == 'active':
        drops = drops.filter(is_active=True)
    elif status_filter == 'deleted':
        drops = drops.filter(is_active=False)

    return render(request, 'admin/drop_list.html', {
        'drops': drops, 'query': query, 'status': status_filter
    })

def admin_drop_delete(request, pk):
    if request.method == 'POST':
        drop = get_object_or_404(Drop, pk=pk)
        
        # 🌟 BORRADO LÓGICO: Solo lo pasamos a falso
        drop.is_active = False 
        drop.save()
        
        messages.success(request, 'Drop desactivado/eliminado correctamente.')
    return redirect('web:admin_drops_list')
def admin_drops_list(request):
    """
    Lista todos los drops en el panel.
    Permite buscar por texto y filtrar por estado (Activos / Inactivos).
    """
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', 'all')
    
    # Traemos todos los registros ordenados por el más reciente
    drops = Drop.objects.all().order_by('-id')

    # Filtro de búsqueda por nombre
    if query:
        drops = drops.filter(name__icontains=query)

    # Filtro de estado basado en el campo is_active
    if status_filter == 'active':
        drops = drops.filter(is_active=True)
    elif status_filter == 'deleted':
        drops = drops.filter(is_active=False)

    return render(request, 'admin/drop_list.html', {
        'drops': drops,
        'query': query,
        'status': status_filter
    })


def admin_drop_new(request):
    """
    Vista para crear un nuevo Drop.
    Maneja la carga de imágenes de campaña mediante request.FILES.
    """
    if request.method == 'POST':
        form = DropAdminForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, '✓ Drop creado exitosamente.')
            return redirect('web:admin_drops_list')
    else:
        form = DropAdminForm()
        
    return render(request, 'admin/drop_new.html', {
        'form': form, 
        'edit_mode': False
    })


def admin_drop_edit(request, pk):
    """
    Vista para modificar un Drop existente.
    Recibe el parámetro 'edit_mode' en True para adaptar los títulos del HTML.
    """
    drop = get_object_or_404(Drop, pk=pk)
    
    if request.method == 'POST':
        form = DropAdminForm(request.POST, request.FILES, instance=drop)
        if form.is_valid():
            form.save()
            messages.success(request, '✓ Drop actualizado correctamente.')
            return redirect('web:admin_drops_list')
    else:
        form = DropAdminForm(instance=drop)
        
    return render(request, 'admin/drop_new.html', {
        'form': form, 
        'edit_mode': True
    })


def admin_drop_delete(request, pk):
    """
    Vista de borrado lógico para Drops.
    Cambia el estado de 'is_active' a False en lugar de removerlo de las tablas.
    """
    if request.method == 'POST':
        drop = get_object_or_404(Drop, pk=pk)
        drop.is_active = False  # Desactivación / Borrado lógico
        drop.save()
        messages.success(request, '✓ Drop desactivado/eliminado correctamente.')
        
    return redirect('web:admin_drops_list')