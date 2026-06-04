import json
import math
from functools import lru_cache
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly, IsAuthenticated

from .models import ShippingZone, PickupPoint, Address
from .serializers import (
    ShippingZoneSerializer,
    ShippingZoneDetailSerializer,
    PickupPointSerializer,
    AddressSerializer,
    ValidateAddressSerializer,
    ShippingOptionsSerializer,
)
from django.conf import settings
import os
from functools import lru_cache as _lru_cache
from urllib.parse import urlencode as _urlencode


def _http_get_json(url, headers=None, timeout=6):
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


@_lru_cache(maxsize=512)
def _forward_geocode(street, city, state, country, limit=6):
    street = (street or '').strip()
    city = (city or '').strip()
    state = (state or '').strip()
    country = (country or 'Argentina').strip()

    headers = {
        'User-Agent': 'BYJosephineCheckout/1.0 (forward-geocoding)',
        'Accept': 'application/json',
    }

    params = {
        'format': 'jsonv2',
        'addressdetails': 1,
        'limit': int(limit or 6),
    }
    if street:
        params['street'] = street
    if city:
        params['city'] = city
    if state:
        params['state'] = state
    if country:
        params['country'] = country

    try:
        url = f'https://nominatim.openstreetmap.org/search?{_urlencode(params)}'
        results = _http_get_json(url, headers=headers, timeout=8)
    except Exception:
        results = []

    output = []
    for item in (results or []):
        lat = item.get('lat')
        lon = item.get('lon')
        display = item.get('display_name')
        address = item.get('address') or {}
        if lat is None or lon is None:
            continue
        output.append({
            'display_name': display,
            'lat': float(lat),
            'lon': float(lon),
            'address': address,
        })

    return output


PROVINCE_QUERY_ALIASES = {
    'buenos aires': 'Provincia de Buenos Aires, Argentina',
    'ciudad autónoma de buenos aires': 'Ciudad Autónoma de Buenos Aires, Argentina',
    'caba': 'Ciudad Autónoma de Buenos Aires, Argentina',
    'cordoba': 'Provincia de Córdoba, Argentina',
    'córdoba': 'Provincia de Córdoba, Argentina',
    'santa fe': 'Provincia de Santa Fe, Argentina',
    'mendoza': 'Provincia de Mendoza, Argentina',
}


@lru_cache(maxsize=64)
def _fetch_cities_for_province(province_name, overpass_timeout=25, nominatim_timeout=6):
    province_name = str(province_name or '').strip()
    if not province_name:
        return []

    headers = {
        'User-Agent': 'BYJosephineCheckout/1.0 (province-cities)',
        'Accept': 'application/json',
    }

    search_term = PROVINCE_QUERY_ALIASES.get(province_name.lower(), f'Provincia de {province_name}, Argentina')

    try:
        nominatim_params = urlencode({
            'q': search_term,
            'format': 'jsonv2',
            'limit': 1,
            'addressdetails': 1,
            'countrycodes': 'ar',
        })
        province_data = _http_get_json(
            f'https://nominatim.openstreetmap.org/search?{nominatim_params}',
            headers=headers,
            timeout=nominatim_timeout,
        )
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
        province_data = []

    province_entry = province_data[0] if province_data else None
    bbox = province_entry.get('boundingbox') if province_entry else None
    if not bbox or len(bbox) != 4:
        return []

    south, north, west, east = map(float, bbox)
    overpass_query = f'''
        [out:json][timeout:{int(overpass_timeout)}];
        (
          node["place"~"city|town|village|suburb|neighbourhood|locality|municipality"]({south},{west},{north},{east});
          way["place"~"city|town|village|suburb|neighbourhood|locality|municipality"]({south},{west},{north},{east});
          relation["place"~"city|town|village|suburb|neighbourhood|locality|municipality"]({south},{west},{north},{east});
        );
        out center tags;
    '''.strip()

    try:
        request = Request(
            'https://overpass-api.de/api/interpreter',
            data=overpass_query.encode('utf-8'),
            headers={
                **headers,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            },
        )
        with urlopen(request, timeout=overpass_timeout) as response:
            overpass_data = json.loads(response.read().decode('utf-8'))
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
        overpass_data = {}

    cities = []
    seen = set()
    for element in (overpass_data.get('elements') or []):
        tags = element.get('tags') or {}
        name = str(tags.get('name') or '').strip()
        if not name:
            continue

        coords = element.get('center') or element
        latitude = coords.get('lat')
        longitude = coords.get('lon')
        if latitude is None or longitude is None:
            continue

        normalized_name = name.lower()
        if normalized_name in seen:
            continue
        seen.add(normalized_name)
        cities.append({
            'name': name,
            'lat': float(latitude),
            'lng': float(longitude),
            'type': str(tags.get('place') or '').strip(),
        })

    cities.sort(key=lambda item: item['name'].lower())

    cities.sort(key=lambda item: item['name'].lower())
    return cities


def _distance_point_to_segment_meters(latitude, longitude, lat1, lon1, lat2, lon2):
    avg_lat = math.radians((latitude + lat1 + lat2) / 3.0)
    cos_lat = max(0.01, math.cos(avg_lat))

    px = longitude * 111320.0 * cos_lat
    py = latitude * 110540.0
    ax = lon1 * 111320.0 * cos_lat
    ay = lat1 * 110540.0
    bx = lon2 * 111320.0 * cos_lat
    by = lat2 * 110540.0

    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5

    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_len_sq))
    cx = ax + t * abx
    cy = ay + t * aby
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


@lru_cache(maxsize=256)
def _reverse_geocode_point(latitude, longitude):
    latitude = round(float(latitude), 6)
    longitude = round(float(longitude), 6)
    headers = {
        'User-Agent': 'BYJosephineCheckout/1.0 (reverse-geocoding)',
        'Accept': 'application/json',
    }

    nominatim_params = urlencode({
        'format': 'jsonv2',
        'lat': latitude,
        'lon': longitude,
        'zoom': 18,
        'addressdetails': 1,
    })

    nominatim_data = {}
    try:
        nominatim_data = _http_get_json(
            f'https://nominatim.openstreetmap.org/reverse?{nominatim_params}',
            headers=headers,
        )
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
        nominatim_data = {}

    address = nominatim_data.get('address') or {}
    road_name = (
        address.get('road')
        or address.get('pedestrian')
        or address.get('residential')
        or address.get('highway')
        or ''
    ).strip()
    house_number = str(address.get('house_number') or '').strip()
    locality = (
        address.get('suburb')
        or address.get('neighbourhood')
        or address.get('city_district')
        or address.get('city')
        or address.get('town')
        or address.get('village')
        or ''
    ).strip()

    streets = []
    overpass_query = f'''
        [out:json][timeout:8];
        (
          way(around:80,{latitude},{longitude})["highway"]["name"];
        );
        out geom;
    '''.strip()

    try:
        overpass_data = _http_get_json(
            'https://overpass-api.de/api/interpreter',
            headers=headers,
            timeout=8,
        )
    except Exception:
        overpass_data = {}

    # Retry with POST when GET was not used above; keep it simple and resilient.
    if not overpass_data:
        try:
            request = Request(
                'https://overpass-api.de/api/interpreter',
                data=overpass_query.encode('utf-8'),
                headers={
                    **headers,
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                },
            )
            with urlopen(request, timeout=8) as response:
                overpass_data = json.loads(response.read().decode('utf-8'))
        except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
            overpass_data = {}

    for element in (overpass_data.get('elements') or []):
        tags = element.get('tags') or {}
        name = str(tags.get('name') or '').strip()
        if not name:
            continue

        geometry = element.get('geometry') or []
        if not geometry:
            continue

        min_distance = None
        for index in range(len(geometry) - 1):
            point_a = geometry[index]
            point_b = geometry[index + 1]
            distance = _distance_point_to_segment_meters(
                latitude,
                longitude,
                point_a.get('lat'),
                point_a.get('lon'),
                point_b.get('lat'),
                point_b.get('lon'),
            )
            if min_distance is None or distance < min_distance:
                min_distance = distance

        if min_distance is not None:
            streets.append((min_distance, name))

    streets.sort(key=lambda item: item[0])
    nearby_streets = []
    seen = set()
    for _, name in streets:
        normalized = name.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        nearby_streets.append(name)
        if len(nearby_streets) >= 3:
            break

    address_parts = []
    if road_name:
        if house_number:
            address_parts.append(f'{road_name} {house_number}')
        else:
            address_parts.append(road_name)

    cross_names = [name for name in nearby_streets if name.lower() != road_name.lower()]
    if road_name and len(cross_names) >= 2:
        address_parts[0] = f'{road_name} entre {cross_names[0]} y {cross_names[1]}'
    elif road_name and cross_names:
        address_parts[0] = f'{road_name} y {cross_names[0]}'

    if locality and locality.lower() not in ' '.join(address_parts).lower():
        address_parts.append(locality)

    formatted_address = ', '.join(address_parts).strip()
    if not formatted_address:
        formatted_address = nominatim_data.get('display_name') or ''

    return {
        'formatted_address': formatted_address,
        'road': road_name,
        'cross_streets': cross_names[:2],
        'locality': locality,
        'raw': nominatim_data,
    }


class ShippingZoneViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ShippingZone.objects.filter(is_active=True)
    serializer_class = ShippingZoneSerializer
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ShippingZoneDetailSerializer
        return ShippingZoneSerializer

    @action(detail=False, methods=['get'])
    def cities(self, request):
        """
        Devuelve una lista de ciudades/localidades dentro de una provincia argentina.
        GET /api/shipping/zones/cities/?province=Buenos%20Aires
        """
        province = str(request.query_params.get('province') or '').strip()
        if not province:
            return Response({'error': 'province es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        # Try to serve from a precomputed JSON cache if available
        cache_path = os.path.join(getattr(settings, 'BASE_DIR', '.'), 'shipping_cities.json')
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as fh:
                    cache = json.load(fh)
                # cache uses province label as keys
                entry = cache.get(province)
                if entry:
                    return Response({
                        'province': province,
                        'cities': entry.get('cities', []),
                        'count': entry.get('count', 0),
                        'cached': True,
                    })
            except Exception:
                # fall back to live fetch below
                pass

        cities = _fetch_cities_for_province(province)
        return Response({
            'province': province,
            'cities': cities,
            'count': len(cities),
            'cached': False,
        })

    @action(detail=False, methods=['get'])
    def cities_all(self, request):
        """
        Devuelve el cache completo con ciudades pre-fetcheadas.
        GET /api/shipping/zones/cities_all/
        """
        cache_path = os.path.join(getattr(settings, 'BASE_DIR', '.'), 'shipping_cities.json')
        if not os.path.exists(cache_path):
            return Response({'error': 'cache_not_found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            with open(cache_path, 'r', encoding='utf-8') as fh:
                cache = json.load(fh)
        except Exception:
            return Response({'error': 'cache_read_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'cached': True, 'provinces': cache})

    @action(detail=False, methods=['get', 'post'])
    def geocode(self, request):
        """
        Forward geocode a structured address using Nominatim.
        GET params: street, city, state, country, limit
        POST JSON: { street, city, state, country, limit }
        """
        if request.method == 'POST':
            data = request.data or {}
            street = data.get('street')
            city = data.get('city')
            state = data.get('state')
            country = data.get('country')
            limit = data.get('limit', 6)
        else:
            street = request.query_params.get('street')
            city = request.query_params.get('city')
            state = request.query_params.get('state')
            country = request.query_params.get('country', 'Argentina')
            limit = request.query_params.get('limit', 6)

        # Basic validation
        if not (street or city):
            return Response({'error': 'Provide at least street or city'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            results = _forward_geocode(street, city, state, country, limit=int(limit or 6))
        except Exception:
            results = []

        return Response({'results': results, 'count': len(results)})

    @action(detail=False, methods=['post'])
    def validate_point(self, request):
        """
        Valida si un punto (lat, lng) está en alguna zona habilitada.
        POST /api/shipping/zones/validate_point/
        Body: { "latitude": -34.9205, "longitude": -57.9496 }
        """
        serializer = ShippingOptionsSerializer(data=request.data)
        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']

            zone = None
            for sz in self.get_queryset():
                if sz.point_in_polygon(latitude, longitude):
                    zone = sz
                    break

            if zone:
                return Response({
                    'valid': True,
                    'zone': ShippingZoneSerializer(zone).data,
                    'shipping_cost': float(zone.shipping_cost),
                    'estimated_days': zone.estimated_days,
                })
            return Response({
                'valid': False,
                'message': 'La dirección está fuera de nuestras zonas de envío.'
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def reverse_geocode(self, request):
        """
        Devuelve una dirección aproximada a partir de un punto del mapa.
        POST /api/shipping/zones/reverse_geocode/
        Body: { "latitude": -34.9205, "longitude": -57.9496 }
        """
        serializer = ShippingOptionsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']
        data = _reverse_geocode_point(latitude, longitude)

        if not data.get('formatted_address'):
            return Response(
                {'valid': False, 'message': 'No pudimos completar la dirección automáticamente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'valid': True,
            'address': data['formatted_address'],
            'road': data.get('road'),
            'cross_streets': data.get('cross_streets', []),
            'locality': data.get('locality'),
        })


class PickupPointViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PickupPoint.objects.filter(is_active=True)
    serializer_class = PickupPointSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=['get'])
    def by_zone(self, request):
        """
        Obtiene puntos de retiro por zona.
        GET /api/shipping/pickup-points/by_zone/?zone_id=1
        """
        zone_id = request.query_params.get('zone_id')
        if not zone_id:
            return Response(
                {'error': 'zone_id es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pickups = self.get_queryset().filter(zone_id=zone_id)
        serializer = self.get_serializer(pickups, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def nearest(self, request):
        """
        Obtiene los puntos de retiro más cercanos.
        POST /api/shipping/pickup-points/nearest/
        Body: { "latitude": -34.9205, "longitude": -57.9496 }
        """
        serializer = ShippingOptionsSerializer(data=request.data)
        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']

            pickups = list(self.get_queryset())
            pickups.sort(
                key=lambda p: ((p.latitude - latitude) ** 2 + (p.longitude - longitude) ** 2) ** 0.5
            )
            top_pickups = pickups[:5]

            serializer = self.get_serializer(top_pickups, many=True)
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(latitude__isnull=False)

    @action(detail=False, methods=['post'])
    def validate(self, request):
        """
        Valida una dirección contra las zonas habilitadas.
        POST /api/shipping/addresses/validate/
        Body: { "address": "Calle 1 123, La Plata", "latitude": -34.9205, "longitude": -57.9496 }
        """
        serializer = ValidateAddressSerializer(data=request.data)
        if serializer.is_valid():
            address_text = serializer.validated_data['address']
            latitude = serializer.validated_data.get('latitude')
            longitude = serializer.validated_data.get('longitude')

            # Si no hay coordenadas, retornar error
            if latitude is None or longitude is None:
                return Response(
                    {'error': 'latitude y longitude son requeridos.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validar que el punto esté en una zona
            zone = None
            for sz in ShippingZone.objects.filter(is_active=True):
                if sz.point_in_polygon(latitude, longitude):
                    zone = sz
                    break

            address, created = Address.objects.update_or_create(
                full_address=address_text,
                defaults={
                    'latitude': latitude,
                    'longitude': longitude,
                    'zone': zone,
                    'is_valid': zone is not None,
                }
            )

            if zone:
                return Response({
                    'address': AddressSerializer(address).data,
                    'valid': True,
                    'zone': ShippingZoneSerializer(zone).data,
                    'shipping_cost': float(zone.shipping_cost),
                    'estimated_days': zone.estimated_days,
                })
            return Response({
                'address': AddressSerializer(address).data,
                'valid': False,
                'message': 'La dirección está fuera de nuestras zonas de envío.'
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
