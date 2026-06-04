from django.db import models
from django.core.validators import MinValueValidator
import json
import math


class ShippingZone(models.Model):
    BORDER_TOLERANCE_METERS = 2.0

    name = models.CharField(max_length=100)
    polygon_geojson = models.TextField(
        blank=True,
        help_text="GeoJSON FeatureCollection con el polígono de la zona"
    )
    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0
    )
    estimated_days = models.IntegerField(default=1, help_text="Días estimados de envío")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_polygon(self):
        """Retorna el polígono como objeto GeoJSON."""
        if self.polygon_geojson:
            return json.loads(self.polygon_geojson)
        return None

    def point_in_polygon(self, latitude, longitude):
        """
        Verifica si un punto (lat, lng) está dentro del polígono.
        Usa algoritmo ray casting simplificado.
        """
        polygon = self.get_polygon()
        if not polygon or polygon['type'] != 'FeatureCollection':
            return False

        for feature in polygon.get('features', []):
            if feature['geometry']['type'] == 'Polygon':
                coords = feature['geometry']['coordinates'][0]
                if self._point_on_polygon_border(latitude, longitude, coords):
                    return True
                if self._point_in_polygon_algorithm(latitude, longitude, coords):
                    return True
        return False

    @classmethod
    def _point_on_polygon_border(cls, lat, lng, polygon_coords):
        """Retorna True si el punto cae sobre alguno de los bordes del polígono."""
        if len(polygon_coords) < 2:
            return False

        for i in range(len(polygon_coords) - 1):
            lon1, lat1 = polygon_coords[i]
            lon2, lat2 = polygon_coords[i + 1]
            if cls._distance_point_to_segment_meters(lat, lng, lat1, lon1, lat2, lon2) <= cls.BORDER_TOLERANCE_METERS:
                return True
        return False

    @staticmethod
    def _distance_point_to_segment_meters(lat, lng, lat1, lng1, lat2, lng2):
        """Distancia aproximada en metros desde un punto a un segmento geográfico."""
        avg_lat = (lat + lat1 + lat2) / 3.0
        cos_lat = max(0.01, math.cos(math.radians(avg_lat)))

        px = lng * 111320.0 * cos_lat
        py = lat * 110540.0
        ax = lng1 * 111320.0 * cos_lat
        ay = lat1 * 110540.0
        bx = lng2 * 111320.0 * cos_lat
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

    @staticmethod
    def _point_in_polygon_algorithm(lat, lng, polygon_coords):
        """Ray casting algorithm para verificar si un punto está en un polígono."""
        x, y = lng, lat
        n = len(polygon_coords)
        inside = False
        p1x, p1y = polygon_coords[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon_coords[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside


class PickupPoint(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=500)
    latitude = models.FloatField()
    longitude = models.FloatField()
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    opening_hours = models.CharField(max_length=100, blank=True, help_text="Ej: Lun-Vie 9-18, Sab 10-14")
    zone = models.ForeignKey(ShippingZone, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.address}"


class Address(models.Model):
    full_address = models.CharField(max_length=500)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    zone = models.ForeignKey(ShippingZone, on_delete=models.SET_NULL, null=True, blank=True)
    is_valid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_address
