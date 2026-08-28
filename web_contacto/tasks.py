"""Tasks de Celery del flujo de contacto público.

Antes eran funciones síncronas en ``emails.py`` que se ejecutaban dentro de la
request: con SMTP lento eso retrasaba la respuesta al visitante. Ahora se
encolan con ``.delay()`` desde ``views.py``.

Reciben PKs, no instancias de modelo: el broker serializa los argumentos como
JSON.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _correo_destino():
    from siteconfig.models import NegocioConfig

    negocio = NegocioConfig.objects.first()
    return negocio.correo if negocio else settings.DEFAULT_FROM_EMAIL


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo_mensaje_contacto(self, mensaje_id):
    """Notifica al correo del negocio sobre un nuevo MensajeContacto."""
    from .models import MensajeContacto

    try:
        mensaje = MensajeContacto.objects.get(pk=mensaje_id)
    except MensajeContacto.DoesNotExist:
        logger.warning("MensajeContacto id=%s ya no existe; se omite el correo.", mensaje_id)
        return

    cuerpo = render_to_string('web_contacto/email/mensaje_contacto.txt', {'mensaje': mensaje})
    try:
        EmailMessage(
            subject=f'Nuevo mensaje de contacto: {mensaje.asunto}',
            body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[_correo_destino()],
            reply_to=[mensaje.correo],
        ).send(fail_silently=False)
    except Exception as exc:
        logger.exception("Fallo al enviar el correo del MensajeContacto id=%s", mensaje_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo_solicitud_cotizacion(self, solicitud_id, cotizacion_id):
    """Notifica al correo del negocio sobre una solicitud de cotización procesada."""
    from servicios.models import Cotizacion

    from .models import SolicitudCotizacionWeb

    try:
        solicitud = SolicitudCotizacionWeb.objects.get(pk=solicitud_id)
        cotizacion = Cotizacion.objects.get(pk=cotizacion_id)
    except (SolicitudCotizacionWeb.DoesNotExist, Cotizacion.DoesNotExist):
        logger.warning(
            "SolicitudCotizacionWeb id=%s o Cotizacion id=%s ya no existe; se omite el correo.",
            solicitud_id, cotizacion_id,
        )
        return

    cuerpo = render_to_string(
        'web_contacto/email/solicitud_cotizacion.txt',
        {'solicitud': solicitud, 'cotizacion': cotizacion},
    )
    try:
        EmailMessage(
            subject=f'Nueva solicitud de cotización web: {cotizacion.numero_oferta}',
            body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[_correo_destino()],
            reply_to=[solicitud.correo_contacto],
        ).send(fail_silently=False)
    except Exception as exc:
        logger.exception(
            "Fallo al enviar el correo de la SolicitudCotizacionWeb id=%s", solicitud_id
        )
        raise self.retry(exc=exc)
