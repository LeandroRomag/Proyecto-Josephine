# Proyecto Josephine

Estructura inicial de un proyecto Django para e-commerce.

## Levantar en local sin Docker

1. Instalar Python 3.12 y MySQL 8 en tu máquina.
2. Crear el entorno virtual e instalar dependencias.

```powershell
.\setup_dev.ps1
```

3. Verificar que MySQL esté corriendo y crear la base de datos definida en `.env`.
4. Revisar `.env` y confirmar estos valores mínimos:

```env
DJANGO_SECRET_KEY=change-me
MYSQL_USER=root
MYSQL_PASSWORD=tu_clave
MYSQL_DATABASE=josephine_db
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
```

5. Ejecutar las migraciones iniciales.

```powershell
python manage.py init_tables
```

6. Levantar el servidor.

```powershell
python manage.py runserver
```

La app quedará disponible en `http://127.0.0.1:8000/`.

## Instalación rápida (Windows)

```powershell
.\setup_dev.ps1
```

Esto crea `.venv`, instala dependencias y copia `.env.example` a `.env` si no existe.

Configurar la conexión MySQL en `.env` (MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_HOST)

Levantado con Docker:

```bash
docker compose up --build
```

Si querés inicializar tablas dentro del contenedor:

```bash
docker compose run --rm web python manage.py init_tables
```

Para inicializar las tablas localmente (crea migraciones y aplica migrate):

```bash
python manage.py init_tables
```

## Limpieza automática de órdenes pendientes

El proyecto incluye un comando que cancela órdenes con pago pendiente después de 60 minutos:

```powershell
python manage.py cleanup_expired_pending_orders
```

En Windows podés registrarlo para que se ejecute cada hora con:

```powershell
.\register_pending_orders_cleanup_task.ps1
```

Si querés cambiar el umbral, el script acepta `-Minutes`.
