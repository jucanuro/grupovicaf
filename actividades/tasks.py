"""Tareas de Celery del calendario (regla 7: el correo nunca va en la request)."""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_aviso_cliente(self, actividad_id):
    """Avisa al cliente de una actividad que le concierne.

    Solo se encola cuando quien guarda marca «Enviar aviso al cliente»: el
    cliente no es participante ni recibe nada por defecto.
    """
    from .models import CalendarioActividad

    actividad = (
        CalendarioActividad.objects.select_related('cliente', 'creado_por')
        .filter(pk=actividad_id).first()
    )
    if not actividad or not actividad.cliente or not actividad.cliente.correo_contacto:
        logger.warning("Aviso de la actividad %s omitido: sin cliente o sin correo.", actividad_id)
        return

    inicio = timezone.localtime(actividad.fecha_inicio)
    fin = timezone.localtime(actividad.fecha_fin)
    cuerpo = render_to_string('actividades/email/aviso_cliente.txt', {
        'actividad': actividad,
        'cliente': actividad.cliente,
        'inicio': inicio,
        'fin': fin,
    })
    try:
        EmailMessage(
            subject=f'GRUPO VICAF · {actividad.titulo} · {inicio:%d/%m/%Y %H:%M}',
            body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[actividad.cliente.correo_contacto],
        ).send(fail_silently=False)
    except Exception as exc:
        logger.exception("Falló el aviso al cliente de la actividad %s", actividad_id)
        raise self.retry(exc=exc)

    CalendarioActividad.objects.filter(pk=actividad_id).update(aviso_cliente_enviado_en=timezone.now())
