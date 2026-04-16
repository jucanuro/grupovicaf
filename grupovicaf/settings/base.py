"""
Configuración Base de Django para el proyecto GRUPO VICAF (LIMS).
Contiene ajustes comunes para todos los entornos.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables del archivo .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env')

# --- CONFIGURACIÓN DE SEGURIDAD Y ENTORNO ---
SECRET_KEY = os.environ.get('SECRET_KEY')

# Apps por defecto y de terceros
INSTALLED_APPS = [
    "jazzmin",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Tus apps
    'core',
    'clientes',
    'trabajadores',
    'servicios',
    'proyectos',
    'actividades',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'grupovicaf.urls'

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
MEDIA_ROOT = BASE_DIR / 'media'

# Login / Logout
LOGIN_REDIRECT_URL = 'dashboard'
LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = 'login'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

JAZZMIN_SETTINGS = {
    "site_title": "VICAF Admin",
    "site_header": "VICAF",
    "site_brand": "VICAF",
    "welcome_sign": "Bienvenido al panel administrativo de VICAF",
    "copyright": "VICAF Systems",
    "show_sidebar": True,
    "navigation_expanded": True,
    "show_ui_builder": False,
    "custom_css": "admin/css/vicaf_admin.css",

    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",

        "servicios": "fas fa-flask",
        "servicios.categoriaservicio": "fas fa-layer-group",
        "servicios.subcategoria": "fas fa-sitemap",
        "servicios.norma": "fas fa-book",
        "servicios.metodo": "fas fa-vial",

        "proyectos": "fas fa-microscope",
        "proyectos.tipomuestra": "fas fa-vials",
        "proyectos.unidadmedida": "fas fa-ruler-combined",
    },

    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    "order_with_respect_to": [
        "auth",
        "auth.user",
        "auth.Group",
        "servicios",
        "servicios.categoriaservicio",
        "servicios.subcategoria",
        "servicios.norma",
        "servicios.metodo",
        "proyectos",
        "proyectos.tipomuestra",
        "proyectos.unidadmedida",
    ],
}
JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "dark_mode_theme": None,
    "navbar_small_text": False,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": False,
    "sidebar_nav_small_text": False,
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-light-primary",
    "sidebar_nav_flat_style": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_collapsible": True,
    "sidebar_nav_animation_speed": 200,
    "sidebar_disable_expand": False,
    "sidebar_no_expand": False,
    "sidebar_mini": False,
    "sidebar_mini_md": False,
    "sidebar_mini_xs": False,
    "nav_accordion": True,
    "nav_accordion_remember_state": True,
    "disable_navtree_expand": False,
}