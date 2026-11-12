"""Tareas Celery del correo (cola 'correo', CLAUDE.md regla 7)."""
import hashlib
import logging

from celery import shared_task
from django.core.files.base import ContentFile
from django.db import transaction

from .mensajeria import carpeta, registrar_evento
from .models import Mensaje
from .servicios import servicio_envio

logger = logging.getLogger(__name__)
MAX_INTENTOS = 5


@shared_task(queue='correo')
def enviar_mensaje(mensaje_id):
    """Bandeja de salida -> Enviados.

    Si el servidor falla de forma temporal (sin conexión, 4xx), el mensaje sigue
    en la Bandeja de salida y se reintenta solo (1, 2, 3, 4 min). Un rechazo
    definitivo o el último intento lo dejan como fallido, con botón Reintentar.
    """
    with transaction.atomic():
        mensaje = Mensaje.objects.select_for_update().select_related('cuenta', 'hilo').filter(
            pk=mensaje_id, estado_envio=Mensaje.EN_COLA,
        ).first()
        if mensaje is None:
            return 'nada que enviar'
        mensaje.intentos += 1
        resultado = servicio_envio().enviar(mensaje)
        campos = ['intentos', 'estado_envio', 'carpeta', 'ultimo_error', 'actualizado_en']
        reintentar = False
        if resultado.ok:
            mensaje.estado_envio = Mensaje.ENVIADO
            mensaje.carpeta = carpeta(mensaje.cuenta, 'enviados')
            mensaje.ultimo_error = resultado.error[:2000]
            if resultado.eml:
                mensaje.eml.save('enviado.eml', ContentFile(resultado.eml), save=False)
                mensaje.eml_sha256 = hashlib.sha256(resultado.eml).hexdigest()
                mensaje.tamano = len(resultado.eml)
                campos += ['eml', 'eml_sha256', 'tamano']
        else:
            mensaje.ultimo_error = resultado.error[:2000]
            reintentar = resultado.reintentar and mensaje.intentos < MAX_INTENTOS
            mensaje.estado_envio = Mensaje.EN_COLA if reintentar else Mensaje.FALLIDO
            logger.warning('Envío fallido del mensaje %s (intento %s): %s', mensaje.pk, mensaje.intentos, resultado.error)
        mensaje.save(update_fields=campos)
        if reintentar:
            espera = 60 * mensaje.intentos
            transaction.on_commit(lambda: enviar_mensaje.apply_async((mensaje_id,), countdown=espera))
    return mensaje.estado_envio


@shared_task(queue='correo')
def traer_mailpit():
    """Solo desarrollo: lo que llegó a Mailpit para las cuentas VICAF entra a sus bandejas."""
    from django.conf import settings

    if not settings.CORREO_MAILPIT_URL:
        return 0
    from .mailpit import traer

    return traer(settings.CORREO_MAILPIT_URL)


@shared_task(queue='correo')
def adjuntar_cotizacion(mensaje_id, cotizacion_id, usuario_id):
    """Genera el PDF de una cotización del LIMS y lo adjunta al borrador."""
    from django.contrib.auth import get_user_model
    from django.test import RequestFactory

    from servicios.views import generar_pdf_cotizacion

    from .mensajeria import agregar_adjunto

    mensaje = Mensaje.objects.filter(pk=mensaje_id, estado_envio=Mensaje.BORRADOR).first()
    usuario = get_user_model().objects.filter(pk=usuario_id).first()
    if mensaje is None or usuario is None:
        return 'borrador no disponible'
    peticion = RequestFactory().get(f'/servicios/cotizaciones/{cotizacion_id}/pdf/')
    peticion.user = usuario
    respuesta = generar_pdf_cotizacion(peticion, cotizacion_id)
    if respuesta.status_code != 200 or respuesta.get('Content-Type') != 'application/pdf':
        logger.warning('No se pudo generar el PDF de la cotización %s (%s)', cotizacion_id, respuesta.status_code)
        return 'error'
    nombre = respuesta['Content-Disposition'].split('filename="')[-1].rstrip('"') or f'Cotizacion_{cotizacion_id}.pdf'
    agregar_adjunto(mensaje, nombre, 'application/pdf', respuesta.content)
    registrar_evento(mensaje.hilo, 'marco', usuario, mensaje, adjunto=nombre, accion='adjuntó cotización')
    return nombre
