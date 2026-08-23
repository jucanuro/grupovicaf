"""
Configuración de Django para el entorno de DESARROLLO.
"""
from .base import *
import os

# --- AJUSTES DE DESARROLLO ---
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']

# En Docker (docker-compose.dev.yml) el servicio 'db' expone Postgres y
# se inyecta DB_HOST=db por entorno. Sin Docker, se sigue usando sqlite3
# (heredado de base.py) para no requerir Postgres local.
if os.environ.get('DB_HOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'grupovicaf'),
            'USER': os.environ.get('DB_USER', 'grupovicaf'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'grupovicaf'),
            'HOST': os.environ.get('DB_HOST'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }

# Log de errores detallado en consola
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}