"""
Configuración de Django para el entorno de DESARROLLO.
"""
from .base import *
import os

# --- AJUSTES DE DESARROLLO ---
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']

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