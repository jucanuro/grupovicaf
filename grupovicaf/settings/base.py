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

    # Tus apps
    'core',
    'clientes',
    'trabajadores',
    'servicios',
    'proyectos',
    'actividades',
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
LOGIN_REDIRECT_URL = 'dashboard'
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

