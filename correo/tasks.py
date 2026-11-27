"""Tareas Celery del correo (cola 'correo', CLAUDE.md regla 7)."""
import hashlib
import logging

from django.utils import timezone
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
        if resultado.ok:
            # Si era el envío de un informe, queda registrado como enviado al cliente (HU-LIMS-47).
            from proyectos.models import InformeFinal
            InformeFinal.objects.filter(mensaje_envio=mensaje.pk).update(
                estado_envio='enviado', fecha_envio=timezone.now(), canal_envio='correo',
            )
            # Igual para una cotización: Pendiente pasa a Enviada cuando el correo sale de verdad (HU-LIMS-50).
            from servicios.models import Cotizacion
            for cot in Cotizacion.objects.filter(mensaje_envio=mensaje.pk, es_plantilla=False):
                cot.canal_envio = 'correo'
                cot.requiere_reenvio = False
                if cot.estado == 'Pendiente':
                    cot.estado = 'Enviada'
                cot.save(update_fields=['canal_envio', 'requiere_reenvio', 'estado', 'fecha_actualizacion'])
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


@shared_task(queue='correo', bind=True, autoretry_for=(OSError,), retry_backoff=30, max_retries=5)
def recibir_entrante(self, clave, para):
    """Paso 4: el .eml que dejó el webhook de Cloudflare entra a la cuenta VICAF.

    Es idempotente (sha256 y Message-ID): un reintento del Worker no duplica.
    El archivo temporal se borra al terminar; si falla algo inesperado queda
    para el siguiente intento.
    """
    from .almacen import almacen_correo
    from .recepcion import CorreoRechazado, recepcion

    try:
        with almacen_correo.open(clave, 'rb') as archivo:
            crudo = archivo.read()
    except FileNotFoundError:
        return 'ya procesado'
    try:
        creados = recepcion().recibir(crudo, destinatarios=[para])
    except CorreoRechazado as error:
        logger.warning('Correo entrante rechazado (%s): %s', clave, error)
        almacen_correo.delete(clave)
        return 'rechazado'
    almacen_correo.delete(clave)
    return len(creados)


@shared_task(bind=True, queue='correo')
def procesar_evento_ses(self, evento):
    """Paso 5: rebote o queja que avisa Amazon SES (vía SNS).

    Rebote permanente -> el mensaje queda «Falló el envío» con el motivo; queja
    -> solo se anota en la bitácora. Los rebotes temporales no cambian nada.
    """
    tipo = evento.get('eventType') or evento.get('notificationType')
    correo = evento.get('mail') or {}
    message_id = (correo.get('commonHeaders') or {}).get('messageId') or ''
    if not message_id:
        for cabecera in correo.get('headers') or []:
            if cabecera.get('name', '').lower() == 'message-id':
                message_id = cabecera.get('value', '')
    estados = (Mensaje.ENVIADO, Mensaje.FALLIDO)
    mensaje = None
    etiquetas = correo.get('tags') or {}
    for valor in etiquetas.get('vicaf_mensaje') or []:
        if str(valor).isdigit():
            mensaje = Mensaje.objects.select_related('hilo').filter(pk=int(valor), estado_envio__in=estados).first()
    if mensaje is None and message_id:
        mensaje = Mensaje.objects.select_related('hilo').filter(message_id=message_id, estado_envio__in=estados).first()
    if mensaje is None:
        # SES puede avisar del rebote antes de que la tarea de envío guarde el
        # message_id (pasa con el simulador): se reintenta unos segundos.
        if (message_id or etiquetas) and not (self.request.called_directly or self.request.is_eager) and self.request.retries < 6:
            raise self.retry(countdown=10, max_retries=6)
        logger.info('Evento SES %s sin mensaje conocido (%s)', tipo, message_id)
        return 'desconocido'
    if tipo == 'Bounce':
        rebote = evento.get('bounce') or {}
        if rebote.get('bounceType') != 'Permanent':
            return 'temporal'
        fallos = []
        for d in rebote.get('bouncedRecipients') or []:
            fallos.append(f"{d.get('emailAddress', '?')}: {d.get('diagnosticCode') or d.get('action') or 'rechazado'}")
        motivo = 'Rebote permanente. ' + '; '.join(fallos)
        mensaje.estado_envio = Mensaje.FALLIDO
        mensaje.ultimo_error = motivo[:2000]
        mensaje.save(update_fields=['estado_envio', 'ultimo_error', 'actualizado_en'])
        registrar_evento(mensaje.hilo, 'marco', None, mensaje, accion='rebote', detalle=motivo[:500])
        return 'rebote'
    if tipo == 'Complaint':
        quejas = [d.get('emailAddress', '?') for d in (evento.get('complaint') or {}).get('complainedRecipients') or []]
        registrar_evento(mensaje.hilo, 'marco', None, mensaje, accion='queja', detalle=', '.join(quejas))
        return 'queja'
    return 'ignorado'
