"""Tareas Celery del correo (cola 'correo', CLAUDE.md regla 7)."""
import logging

from celery import shared_task
from django.db import transaction

from .mensajeria import carpeta, registrar_evento
from .models import Mensaje
from .servicios import servicio_envio

logger = logging.getLogger(__name__)
MAX_INTENTOS = 5


@shared_task(queue='correo')
def enviar_mensaje(mensaje_id):
    """Bandeja de salida -> Enviados (o queda como fallido para reintentar)."""
    with transaction.atomic():
        mensaje = Mensaje.objects.select_for_update().select_related('cuenta', 'hilo').filter(
            pk=mensaje_id, estado_envio=Mensaje.EN_COLA,
        ).first()
        if mensaje is None:
            return 'nada que enviar'
        mensaje.intentos += 1
        resultado = servicio_envio().enviar(mensaje)
        if resultado.ok:
            mensaje.estado_envio = Mensaje.ENVIADO
            mensaje.carpeta = carpeta(mensaje.cuenta, 'enviados')
            mensaje.ultimo_error = ''
        else:
            mensaje.estado_envio = Mensaje.FALLIDO
            mensaje.ultimo_error = resultado.error[:2000]
            logger.warning('Envío fallido del mensaje %s: %s', mensaje.pk, resultado.error)
        mensaje.save(update_fields=['intentos', 'estado_envio', 'carpeta', 'ultimo_error', 'actualizado_en'])
    return mensaje.estado_envio


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
