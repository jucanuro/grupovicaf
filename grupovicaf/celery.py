"""
App de Celery para GRUPO VICAF.

Un único worker sirve a ambos SITE_ROLE ('lab' y 'web'): las tareas asíncronas
(hoy, el procesamiento del InformeFinal) operan sobre la misma base de datos
sin importar qué sitio encoló la tarea.
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grupovicaf.settings.dev')

app = Celery('grupovicaf')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
