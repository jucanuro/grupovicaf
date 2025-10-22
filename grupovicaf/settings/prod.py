"""
Configuración de Django para el entorno de PRODUCCIÓN.
"""
from .base import *

# --- AJUSTES DE PRODUCCIÓN ---
DEBUG = False # Siempre False en producción

# Hosts permitidos (DEBE ser configurado)
ALLOWED_HOSTS = ['grupovicaf.com', 'www.grupovicaf.com', 'tu-ip-servidor']

# --- SEGURIDAD AVANZADA (Requerido en producción) ---
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# HSTS (HTTP Strict Transport Security) - Descomentar en despliegue final
# SECURE_HSTS_SECONDS = 31536000 
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
# X-Frame-Options: Deny (ya está en el middleware)

# Configuración de base de datos para producción (ej. PostgreSQL o MySQL)
# DATABASES = {
#     'default': env.db('DATABASE_URL')
# }

# Log de errores a archivos o servicios externos
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/grupovicaf_prod_warnings.log', # Cambia esta ruta
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': True,
        },
    },
}