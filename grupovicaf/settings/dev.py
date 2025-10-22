"""
Configuración de Django para el entorno de DESARROLLO.
"""
from .base import *

# --- AJUSTES DE DESARROLLO ---
DEBUG = os.environ.get('DEBUG', 'True') == 'True' # Leer de .env

ALLOWED_HOSTS = ['*']

# Opcional: Para usar Django Debug Toolbar (requiere instalación)
# INTERNAL_IPS = [
#     '127.0.0.1',
# ]

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