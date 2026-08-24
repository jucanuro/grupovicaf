"""Envío de correos del flujo de contacto, fuera de la vista a propósito.

TODO (Fase 8 / Celery): convertir enviar_correo_mensaje_contacto y
enviar_correo_solicitud_cotizacion en tasks (@shared_task) y reemplazar las
llamadas directas en views.py por .delay(). Hoy se ejecutan de forma síncrona
dentro de la request; con SMTP lento eso retrasa la respuesta al visitante.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from siteconfig.models import NegocioConfig

logger = logging.getLogger(__name__)


def _correo_destino():
    negocio = NegocioConfig.objects.first()
    return negocio.correo if negocio else settings.DEFAULT_FROM_EMAIL


def enviar_correo_mensaje_contacto(mensaje):
    """Notifica al correo del negocio sobre un nuevo MensajeContacto."""
    try:
        cuerpo = render_to_string('web_contacto/email/mensaje_contacto.txt', {'mensaje': mensaje})
        EmailMessage(
            subject=f'Nuevo mensaje de contacto: {mensaje.asunto}',
            body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[_correo_destino()],
            reply_to=[mensaje.correo],
        ).send(fail_silently=False)
    except Exception:
        logger.exception('No se pudo enviar el correo de notificación de MensajeContacto id=%s', mensaje.pk)


def enviar_correo_solicitud_cotizacion(solicitud, cotizacion):
    """Notifica al correo del negocio sobre una nueva solicitud de cotización procesada."""
    try:
        cuerpo = render_to_string(
            'web_contacto/email/solicitud_cotizacion.txt',
            {'solicitud': solicitud, 'cotizacion': cotizacion},
        )
        EmailMessage(
            subject=f'Nueva solicitud de cotización web: {cotizacion.numero_oferta}',
            body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[_correo_destino()],
            reply_to=[solicitud.correo_contacto],
        ).send(fail_silently=False)
    except Exception:
        logger.exception('No se pudo enviar el correo de notificación de SolicitudCotizacionWeb id=%s', solicitud.pk)
