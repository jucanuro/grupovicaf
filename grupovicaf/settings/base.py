"""
Configuración Base de Django para el proyecto GRUPO VICAF (LIMS).
Contiene ajustes comunes para todos los entornos.
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Cargar variables del archivo .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env')

# --- CONFIGURACIÓN DE SEGURIDAD Y ENTORNO ---
SECRET_KEY = os.environ.get('SECRET_KEY')

# --- ROL DEL SITIO: 'lab' (LIMS) o 'web' (institucional pública) ---
SITE_ROLE = os.environ.get('SITE_ROLE', 'lab')
if SITE_ROLE not in ('lab', 'web'):
    raise ImproperlyConfigured(f"SITE_ROLE inválido: {SITE_ROLE}")
ROOT_URLCONF = f'grupovicaf.urls_{SITE_ROLE}'
SESSION_COOKIE_NAME = f'gv_{SITE_ROLE}_sessionid'
CSRF_COOKIE_NAME = f'gv_{SITE_ROLE}_csrftoken'
# Los tests de las apps web_* usan urls_web.py con cualquier SITE_ROLE.
TEST_RUNNER = 'grupovicaf.test_runner.SiteRoleTestRunner'
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000')

# Interruptor de indexación para el rol 'web' (regla 15 + fase de
# despliegue): en True, todas las páginas públicas emiten noindex,nofollow
# y robots.txt devuelve Disallow: / sin importar el noindex de cada página.
# Se apaga (SITE_NOINDEX=False en .env) cuando el contenido esté listo para
# salir a producción.
SITE_NOINDEX = os.environ.get('SITE_NOINDEX', 'True') == 'True'

# Apps por defecto y de terceros
INSTALLED_APPS = [
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.postgres',

    # Tus apps
    'core',
    'clientes',
    'trabajadores',
    'servicios',
    'proyectos',
    'actividades',
    'analisis',
    'correo',
    'siteconfig',
    'web_inicio',
    'web_nosotros',
    'web_acreditacion',
    'web_catalogo',
    'web_contacto',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'correo.middleware.CorreoHostMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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
                'trabajadores.context_processors.permisos_usuario',
                'grupovicaf.context_processors.site_url',
                'siteconfig.context_processors.negocio',
                'web_catalogo.context_processors.footer_lineas',
            ],
        },
    },
]

WSGI_APPLICATION = 'grupovicaf.wsgi.application'

# Base de Datos por defecto (local)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Validadores de contraseña
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internacionalización y Zona Horaria (Perú)
LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True

# Archivos estáticos
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Archivos media
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'mediafiles'

# Login / Logout
# Tras el login se muestra la pantalla de entrada (tarjetas Correos / Sistema,
# app correo). Si el usuario venía de una URL concreta (?next=), va ahí.
LOGIN_REDIRECT_URL = 'inicio'
LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = 'login'

# Cache (Redis, DB 0). Usado por web_catalogo en las vistas de listado
# (15 min, ver web_catalogo/cache.py); aún no se usa para sesiones.
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}


def _redis_db(url, db):
    """Misma instancia de Redis que ``url`` pero en otra base lógica."""
    return re.sub(r'/\d+\Z', f'/{db}', url, count=1)


# --- Celery ---
# Toda tarea de más de ~1s (PDF, QR, correo, SMS) va aquí en vez de bloquear
# la request. Comparte la instancia de Redis con el cache pero en otra base
# lógica (DB 1): así un FLUSHDB del cache no se lleva por delante la cola.
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or _redis_db(REDIS_URL, 1)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or _redis_db(REDIS_URL, 1)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
# Silencia el CPendingDeprecationWarning de Celery 5.x: reintenta la conexión
# con el broker durante el arranque del worker (comportamiento por defecto en 6.0).
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# --- Email ---
# Sin valores en el código (regla 6): todo viene de .env; ver .env.example.
# Sin EMAIL_HOST (dev local) los correos se imprimen en consola en vez de
# tumbar el worker de Celery.
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT') or 587)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@grupovicaf.com')
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST
    else 'django.core.mail.backends.console.EmailBackend',
)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Módulo de correo (app correo, VCF-LIMS) ---
# El mismo proceso del rol 'lab' sirve dos hosts: el LIMS (LAB_HOST) y el
# correo (CORREO_HOST). correo.middleware.CorreoHostMiddleware elige el
# URLconf según el host. Las cookies NO se comparten entre hosts (regla 5):
# el paso de uno a otro usa un enlace firmado de un solo uso.
CORREO_HOST = os.environ.get('CORREO_HOST') or 'email.localhost'
LAB_HOST = os.environ.get('LAB_HOST') or 'localhost'
# URLs base absolutas (con esquema y puerto). Vacías = se arman con el
# esquema y el puerto de la petición actual (cómodo en desarrollo).
CORREO_BASE_URL = os.environ.get('CORREO_BASE_URL', '').rstrip('/')
LAB_BASE_URL = os.environ.get('LAB_BASE_URL', '').rstrip('/')
# Vigencia del enlace firmado laboratorio -> correo, en segundos.
CORREO_ENLACE_SEGUNDOS = int(os.environ.get('CORREO_ENLACE_SEGUNDOS') or 60)
# Si el usuario solo tiene acceso a un módulo, saltar la pantalla de entrada.
CORREO_OMITIR_ENTRADA = os.environ.get('CORREO_OMITIR_ENTRADA', 'False') == 'True'
# Dónde van los .eml y adjuntos: 'local' (carpeta privada, dev y pruebas) o
# 'r2' (bucket PRIVADO de Cloudflare R2 vía django-storages, producción).
CORREO_ALMACEN = os.environ.get('CORREO_ALMACEN') or 'local'
# Carpeta privada del modo 'local'. Fuera de MEDIA_ROOT: nunca la sirve nginx.
CORREO_ALMACEN_DIR = os.environ.get('CORREO_ALMACEN_DIR') or str(BASE_DIR / 'correo_privado')
# Modo 'r2': bucket, endpoint S3 de la cuenta (https://<id>.r2.cloudflarestorage.com)
# y un token de API de R2 con permiso solo sobre ese bucket.
CORREO_R2_BUCKET = os.environ.get('CORREO_R2_BUCKET', '')
CORREO_R2_ENDPOINT = os.environ.get('CORREO_R2_ENDPOINT', '').rstrip('/')
CORREO_R2_ACCESS_KEY = os.environ.get('CORREO_R2_ACCESS_KEY', '')
CORREO_R2_SECRET_KEY = os.environ.get('CORREO_R2_SECRET_KEY', '')
# Dominios que puede tener una cuenta creada desde «Administrar cuentas».
CORREO_DOMINIOS = [d.strip().lower() for d in (os.environ.get('CORREO_DOMINIOS') or 'grupovicaf.com').split(',') if d.strip()]
# Vigencia de los enlaces firmados de descarga y de las URL prefirmadas de R2.
CORREO_URL_FIRMADA_SEGUNDOS = int(os.environ.get('CORREO_URL_FIRMADA_SEGUNDOS') or 300)
# Límite total de adjuntos al redactar.
CORREO_MAX_ADJUNTOS_BYTES = 25 * 1024 * 1024
# Envío: 'simulado' (no sale nada) o 'smtp'. En dev el SMTP es Mailpit
# (docker-compose.dev.yml); en producción, el SMTP de Amazon SES (Paso 5).
# Es un SMTP aparte de EMAIL_* (avisos del sistema y formulario de contacto).
CORREO_ENVIO = os.environ.get('CORREO_ENVIO') or 'simulado'
CORREO_SMTP_HOST = os.environ.get('CORREO_SMTP_HOST', '')
CORREO_SMTP_PUERTO = int(os.environ.get('CORREO_SMTP_PUERTO') or 587)
CORREO_SMTP_USUARIO = os.environ.get('CORREO_SMTP_USUARIO', '')
CORREO_SMTP_CLAVE = os.environ.get('CORREO_SMTP_CLAVE', '')
CORREO_SMTP_TLS = os.environ.get('CORREO_SMTP_TLS', 'True') == 'True'
# Solo desarrollo: API de Mailpit. Con valor, beat trae cada 15 s lo que llegó
# a las cuentas VICAF (hace las veces de Cloudflare Email Routing).
CORREO_MAILPIT_URL = os.environ.get('CORREO_MAILPIT_URL', '').rstrip('/')
# Tamaño máximo de un correo entrante completo (.eml).
CORREO_MAX_ENTRANTE_BYTES = 40 * 1024 * 1024

