import os
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'change-me')
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'

def _build_allowed_hosts():
    hosts = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost').split(',') if host.strip()]
    site_url = os.getenv('SITE_URL', '').strip()
    if site_url:
        parsed = urlparse(site_url)
        if parsed.hostname and parsed.hostname not in hosts:
            hosts.append(parsed.hostname)
    return hosts


ALLOWED_HOSTS = _build_allowed_hosts()

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'core',
    'users',
    'products',
    'orders',
    'shipping',
    'payments',
    'cart',
    'promotions',
    'api',
    'web',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'main.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'web.context_processors.global_categories',
                'web.context_processors.global_whatsapp_contact',
            ],
        },
    },
]

WSGI_APPLICATION = 'main.wsgi.application'

# Database: MySQL (configure via .env)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('MYSQL_DATABASE', 'josephine_db'),
        'USER': os.getenv('MYSQL_USER', 'root'),
        'PASSWORD': os.getenv('MYSQL_PASSWORD', ''),
        'HOST': os.getenv('MYSQL_HOST', '127.0.0.1'),
        'PORT': os.getenv('MYSQL_PORT', '3306'),
    }
}

AUTH_USER_MODEL = 'users.User'
AUTHENTICATION_BACKENDS = [
    'users.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
]

LANGUAGE_CODE = 'es-AR'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Configuration
cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS', '')

if cors_origins_env:
    # Separa los dominios por coma y elimina espacios vacíos
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_env.split(',') if origin.strip()]
else:
    # Valores por defecto para tu entorno de desarrollo local
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Email Configuration (for password reset and transactional emails)
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_FROM = os.getenv('EMAIL_FROM', 'noreply@josephineshop.com')
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', 10))

# Frontend URL for password reset links
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

# Mercado Pago
MERCADOPAGO_ACCESS_TOKEN = os.getenv('MERCADOPAGO_ACCESS_TOKEN', '')
MERCADOPAGO_PUBLIC_KEY = os.getenv('MERCADOPAGO_PUBLIC_KEY', '')
MERCADOPAGO_WEBHOOK_SECRET = os.getenv('MERCADOPAGO_WEBHOOK_SECRET', '')
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8000')

# Media / Storage configuration (MinIO / S3 compatible)
# Use django-storages S3 backend when USE_MINIO is true.
USE_MINIO = os.getenv('USE_MINIO', 'false').lower() in ('1', 'true', 'yes')
if USE_MINIO:
    # ensure django-storages is available in INSTALLED_APPS when enabled
    if 'storages' not in INSTALLED_APPS:
        INSTALLED_APPS.append('storages')

    # Minimal required settings for MinIO/S3-compatible backend
    DEFAULT_FILE_STORAGE = os.getenv('DEFAULT_FILE_STORAGE', 'storages.backends.s3boto3.S3Boto3Storage')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')

    # Optional values: convert empty strings to None so boto3 doesn't choke
    _region = os.getenv('AWS_S3_REGION_NAME', '')
    AWS_S3_REGION_NAME = _region if _region else None

    _addressing = os.getenv('AWS_S3_ADDRESSING_STYLE', '')
    if _addressing:
        AWS_S3_ADDRESSING_STYLE = _addressing

    _sig = os.getenv('AWS_S3_SIGNATURE_VERSION', '')
    if _sig:
        AWS_S3_SIGNATURE_VERSION = _sig

    AWS_S3_SECURE = os.getenv('AWS_S3_SECURE', 'false').lower() in ('1', 'true', 'yes')

    # Optional ACL/custom domain: treat literal 'None' or empty as None
    _acl = os.getenv('AWS_DEFAULT_ACL', '')
    AWS_DEFAULT_ACL = None if _acl in ('', 'None', None) else _acl
    _custom = os.getenv('AWS_S3_CUSTOM_DOMAIN', '')
    AWS_S3_CUSTOM_DOMAIN = _custom if _custom else None
else:
    DEFAULT_FILE_STORAGE = os.getenv('DEFAULT_FILE_STORAGE', 'django.core.files.storage.FileSystemStorage')

# Media URL and root (used when not using S3 storage)
MEDIA_URL = os.getenv('MEDIA_URL', '/media/')
MEDIA_ROOT = os.getenv('MEDIA_ROOT', BASE_DIR / 'media')

SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG