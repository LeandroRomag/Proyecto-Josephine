from django.core.management.base import BaseCommand
from shipping.models import ShippingZone, PickupPoint
import json


# Polígonos aproximados para las zonas de envío en GeoJSON.
# Se prioriza cubrir Tolosa, Villa Argüello, El Carmen, Punta Lara, City Bell, Gonnet, Villa Elisa y Los Talas.
ZONES_DATA = [
    {
        "name": "La Plata",
        "estimated_days": 1,
        "shipping_cost": 200,
        "center": {"lat": -34.915, "lng": -57.955},
        "polygon_geojson": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [-58.0950, -34.8450],
                            [-57.8950, -34.8450],
                            [-57.8750, -34.8800],
                            [-57.8720, -34.9100],
                            [-57.8800, -34.9350],
                            [-57.9000, -34.9550],
                            [-57.9500, -34.9650],
                            [-58.0150, -34.9780],
                            [-58.0900, -34.9550],
                            [-58.0950, -34.8450]
                        ]]
                    }
                }
            ]
        }
    },
    {
        "name": "Berisso",
        "estimated_days": 2,
        "shipping_cost": 300,
        "center": {"lat": -34.912, "lng": -57.894},
        "polygon_geojson": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [-57.9300, -34.8450],
                            [-57.9000, -34.8450],
                            [-57.8600, -34.8600],
                            [-57.8500, -34.8900],
                            [-57.8400, -34.9150],
                            [-57.8300, -34.9420],
                            [-57.9050, -34.9380],
                            [-57.9300, -34.9200],
                            [-57.9300, -34.8450]
                        ]]
                    }
                }
            ]
        }
    },
    {
        "name": "Ensenada",
        "estimated_days": 2,
        "shipping_cost": 350,
        "center": {"lat": -34.842, "lng": -57.944},
        "polygon_geojson": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [-58.0000, -34.8050],
                            [-58.0000, -34.8050],
                            [-57.9500, -34.8050],
                            [-57.9200, -34.8150],
                            [-57.9000, -34.8350],
                            [-57.8950, -34.8450],
                            [-57.9200, -34.8460],
                            [-57.9650, -34.8400],
                            [-57.9900, -34.8280],
                            [-58.0000, -34.8050]
                        ]]
                    }
                }
            ]
        }
    }
]

PICKUP_POINTS_DATA = [
    {
        "name": "Retiro Central La Plata",
        "address": "Calle 7 entre 47 y 48, La Plata",
        "latitude": -34.9205,
        "longitude": -57.9496,
        "phone": "0221-4222222",
        "opening_hours": "Lun-Vie 9:00-18:00, Sab 10:00-14:00",
        "zone_name": "La Plata"
    },
    {
        "name": "Retiro Diagonal 80",
        "address": "Diagonal 80 entre 7 y 8, La Plata",
        "latitude": -34.9300,
        "longitude": -57.9500,
        "phone": "0221-4111111",
        "opening_hours": "Lun-Vie 8:00-19:00, Sab 9:00-15:00",
        "zone_name": "La Plata"
    },
    {
        "name": "Retiro Berisso",
        "address": "Av. Mitre 350, Berisso",
        "latitude": -34.8685,
        "longitude": -58.2643,
        "phone": "0221-4600000",
        "opening_hours": "Lun-Vie 9:00-17:00",
        "zone_name": "Berisso"
    },
    {
        "name": "Retiro Ensenada",
        "address": "Calle 1 esquina 118, Ensenada",
        "latitude": -34.8508,
        "longitude": -58.3352,
        "phone": "0221-4700000",
        "opening_hours": "Lun-Vie 10:00-18:00",
        "zone_name": "Ensenada"
    }
]


class Command(BaseCommand):
    help = 'Carga las zonas de envío (Berisso, Ensenada, La Plata) y puntos de retiro.'

    def handle(self, *args, **options):
        # Cargar zonas
        for zone_data in ZONES_DATA:
            zone, created = ShippingZone.objects.get_or_create(
                name=zone_data['name'],
                defaults={
                    'estimated_days': zone_data['estimated_days'],
                    'shipping_cost': zone_data['shipping_cost'],
                    'polygon_geojson': json.dumps(zone_data['polygon_geojson']),
                    'is_active': True,
                }
            )
            if not created:
                zone.estimated_days = zone_data['estimated_days']
                zone.shipping_cost = zone_data['shipping_cost']
                zone.polygon_geojson = json.dumps(zone_data['polygon_geojson'])
                zone.is_active = True
                zone.save(update_fields=['estimated_days', 'shipping_cost', 'polygon_geojson', 'is_active', 'updated_at'])
            status = "✓ Creada" if created else "✓ Ya existe"
            self.stdout.write(f"{status}: Zona '{zone.name}'")

        # Cargar puntos de retiro
        for pickup_data in PICKUP_POINTS_DATA:
            zone = ShippingZone.objects.get(name=pickup_data['zone_name'])
            pickup, created = PickupPoint.objects.get_or_create(
                name=pickup_data['name'],
                defaults={
                    'address': pickup_data['address'],
                    'latitude': pickup_data['latitude'],
                    'longitude': pickup_data['longitude'],
                    'phone': pickup_data['phone'],
                    'opening_hours': pickup_data['opening_hours'],
                    'zone': zone,
                    'is_active': True,
                }
            )
            if not created:
                pickup.address = pickup_data['address']
                pickup.latitude = pickup_data['latitude']
                pickup.longitude = pickup_data['longitude']
                pickup.phone = pickup_data['phone']
                pickup.opening_hours = pickup_data['opening_hours']
                pickup.zone = zone
                pickup.is_active = True
                pickup.save(update_fields=['address', 'latitude', 'longitude', 'phone', 'opening_hours', 'zone', 'is_active'])
            status = "✓ Creado" if created else "✓ Ya existe"
            self.stdout.write(f"{status}: Punto de retiro '{pickup.name}'")

        self.stdout.write(self.style.SUCCESS('\n✅ Zonas de envío y puntos de retiro cargados correctamente.'))
