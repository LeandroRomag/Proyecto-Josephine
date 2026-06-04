# API de Logística - Documentación de Endpoints

## Zonas de Envío

### Listar todas las zonas activas
```
GET /api/shipping/zones/
```
**Respuesta:**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "name": "La Plata",
      "shipping_cost": "200.00",
      "estimated_days": 1,
      "is_active": true
    }
  ]
}
```

### Validar si un punto está en una zona
```
POST /api/shipping/zones/validate_point/
Content-Type: application/json

{
  "latitude": -34.9205,
  "longitude": -57.9496
}
```

**Respuesta exitosa (200):**
```json
{
  "valid": true,
  "zone": {
    "id": 1,
    "name": "La Plata",
    "shipping_cost": "200.00",
    "estimated_days": 1,
    "is_active": true
  },
  "shipping_cost": 200.0,
  "estimated_days": 1
}
```

**Respuesta fallida (400):**
```json
{
  "valid": false,
  "message": "La dirección está fuera de nuestras zonas de envío."
}
```

---

## Puntos de Retiro

### Listar todos los puntos de retiro activos
```
GET /api/shipping/pickup-points/
```

### Obtener puntos de retiro por zona
```
GET /api/shipping/pickup-points/by_zone/?zone_id=1
```

**Respuesta:**
```json
[
  {
    "id": 1,
    "name": "Retiro Central La Plata",
    "address": "Calle 7 entre 47 y 48, La Plata",
    "latitude": -34.9205,
    "longitude": -57.9496,
    "phone": "0221-4222222",
    "email": "",
    "opening_hours": "Lun-Vie 9:00-18:00, Sab 10:00-14:00",
    "zone": 1,
    "zone_name": "La Plata",
    "is_active": true
  }
]
```

### Obtener los 5 puntos de retiro más cercanos
```
POST /api/shipping/pickup-points/nearest/
Content-Type: application/json

{
  "latitude": -34.9205,
  "longitude": -57.9496
}
```

---

## Direcciones de Envío

### Validar una dirección
```
POST /api/shipping/addresses/validate/
Content-Type: application/json

{
  "address": "Calle 1 123, La Plata",
  "latitude": -34.9205,
  "longitude": -57.9496
}
```

**Respuesta exitosa (200):**
```json
{
  "address": {
    "id": 1,
    "full_address": "Calle 1 123, La Plata",
    "latitude": -34.9205,
    "longitude": -57.9496,
    "zone": 1,
    "zone_name": "La Plata",
    "shipping_cost": "200.00",
    "estimated_days": 1,
    "is_valid": true,
    "created_at": "2026-05-15T10:30:00Z"
  },
  "valid": true,
  "zone": {
    "id": 1,
    "name": "La Plata",
    "shipping_cost": "200.00",
    "estimated_days": 1,
    "is_active": true
  },
  "shipping_cost": 200.0,
  "estimated_days": 1
}
```

**Respuesta fallida (400):**
```json
{
  "address": {
    "id": 2,
    "full_address": "Calle 1 123, Otro Lugar",
    "latitude": -35.0,
    "longitude": -58.0,
    "zone": null,
    "zone_name": null,
    "shipping_cost": null,
    "estimated_days": null,
    "is_valid": false,
    "created_at": "2026-05-15T10:31:00Z"
  },
  "valid": false,
  "message": "La dirección está fuera de nuestras zonas de envío."
}
```

---

## Zonas Disponibles

### La Plata
- **Costo de envío:** $200
- **Días estimados:** 1
- **Coordenadas centro:** -34.9205, -57.9496
- **Puntos de retiro:** Retiro Central La Plata, Retiro Diagonal 80

### Berisso
- **Costo de envío:** $300
- **Días estimados:** 2
- **Coordenadas centro:** -34.8685, -58.2643
- **Puntos de retiro:** Retiro Berisso

### Ensenada
- **Costo de envío:** $350
- **Días estimados:** 2
- **Coordenadas centro:** -34.8508, -58.3352
- **Puntos de retiro:** Retiro Ensenada

---

## Flujo de Validación Geográfica

```
1. Cliente selecciona dirección de envío
   ↓
2. Frontend obtiene coordenadas (GPS, Google Maps, Mapbox, etc.)
   ↓
3. POST /api/shipping/addresses/validate/ con dirección + coords
   ↓
4. Backend valida si está en zona habilitada usando ray casting
   ↓
5. Si válida: Se retorna zona, costo y días
   Si no: Se rechaza y se puede sugerir puntos de retiro
```

---

## Integración en el Checkout

1. **Paso 1: Selección de método de envío**
   - GET /api/shipping/zones/ (mostrar opciones a domicilio)
   - GET /api/shipping/pickup-points/ (mostrar puntos de retiro)

2. **Paso 2: Validación de dirección**
   - POST /api/shipping/addresses/validate/ (con ubicación del cliente)

3. **Paso 3: Cálculo de costo total**
   - Total del carrito + shipping_cost de la zona validada

4. **Paso 4: Confirmación**
   - Guardar dirección validada en la orden
