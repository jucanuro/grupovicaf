"""
Configuración Base de Django para el proyecto GRUPO VICAF (LIMS).
Contiene ajustes comunes para todos los entornos.
"""
import os
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

# Cache (Redis). Usado por web_catalogo en las vistas de listado (15 min,
# ver web_catalogo/cache.py); aún no se usa para sesiones.
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

