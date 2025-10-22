"""
Configuración WSGI para el proyecto grupovicaf.
"""

import os
from django.core.wsgi import get_wsgi_application

# Apunta a la configuración de PRODUCCIÓN
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grupovicaf.settings.prod')

application = get_wsgi_application()