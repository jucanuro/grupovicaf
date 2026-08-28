"""
App de Celery para GRUPO VICAF.

Un único worker sirve a ambos SITE_ROLE ('lab' y 'web'): las tareas asíncronas
(hoy, el procesamiento del InformeFinal) operan sobre la misma base de datos
sin importar qué sitio encoló la tarea.
"""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grupovicaf.settings.dev')

app = Celery('grupovicaf')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Tareas periódicas. Las ejecuta el servicio `beat` (ver docker-compose);
# los horarios van en CELERY_TIMEZONE (America/Lima).
app.conf.beat_schedule = {
    'proyectos-vencidos-diario': {
        'task': 'proyectos.tasks.notificar_proyectos_vencidos',
        'schedule': crontab(hour=7, minute=30),
    },
}
