"""Operaciones del correo que usan las vistas, la semilla de ejemplo y, más
adelante, ServicioRecepcion (Paso 4) y el importador IMAP (Paso 6).

- hilos por Message-ID / In-Reply-To / References (respaldo: asunto normalizado
  de los últimos 30 días en la misma cuenta);
- contactos y su vínculo opcional con un cliente del LIMS;
- bitácora (EventoMensaje);
- carpetas del sistema de cada cuenta.
"""
import hashlib
import re
import uuid
from datetime import timedelta
from email.utils import getaddresses

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from clientes.models import Cliente

from .busqueda import indexar
from .models import Adjunto, Carpeta, Contacto, EventoMensaje, Hilo, Mensaje
from .sanitizar import html_a_texto, sanitizar_html, texto_a_html, vista_previa

NOMBRES_CARPETAS = dict(Carpeta.TIPOS)
ORDEN_CARPETAS = {t: i for i, t in enumerate(Carpeta.DEL_SISTEMA)}
_PREFIJOS = re.compile(r'^\s*((re|rv|fw|fwd|reenviar|resp)\s*(\[\d+\])?\s*:\s*)+', re.IGNORECASE)


def asegurar_carpetas(cuenta):
    for tipo in Carpeta.DEL_SISTEMA:
        Carpeta.objects.get_or_create(
            cuenta=cuenta, tipo=tipo,
            defaults={'nombre': NOMBRES_CARPETAS[tipo], 'orden': ORDEN_CARPETAS[tipo]},
        )


def carpeta(cuenta, tipo):
    asegurar_carpetas(cuenta)
    return Carpeta.objects.get(cuenta=cuenta, tipo=tipo)


def normalizar_asunto(asunto):
    return _PREFIJOS.sub('', asunto or '').strip()


def nuevo_message_id(cuenta):
    dominio = cuenta.direccion.split('@')[-1]
    return f'<{uuid.uuid4().hex}@{dominio}>'


def direcciones(texto):
    """'Ana <ana@x.com>, b@y.com' -> [{'nombre': 'Ana', 'correo': 'ana@x.com'}, ...]"""
    resultado, vistos = [], set()
    for nombre, correo in getaddresses([texto or '']):
        correo = correo.strip().lower()
        if '@' in correo and correo not in vistos:
            vistos.add(correo)
            resultado.append({'nombre': nombre.strip(), 'correo': correo})
    return resultado


def contacto_para(correo, nombre=''):
    correo = (correo or '').strip().lower()
    contacto, creado = Contacto.objects.get_or_create(correo=correo, defaults={'nombre': nombre or ''})
    if creado or (not contacto.nombre and nombre):
        if nombre and not contacto.nombre:
            contacto.nombre = nombre
        if contacto.cliente_id is None:
            cliente = Cliente.objects.filter(correo_contacto__iexact=correo).only('pk', 'razon_social').first()
            if cliente:
                contacto.cliente = cliente
                contacto.empresa = contacto.empresa or cliente.razon_social
        contacto.save()
    return contacto


def _referencias(texto):
    return re.findall(r'<[^<>\s]+>', texto or '')


def hilo_para(cuenta, *, asunto, fecha, in_reply_to='', references=''):
    ids = _referencias(references) + _referencias(in_reply_to)
    if ids:
        previo = Mensaje.objects.filter(cuenta=cuenta, message_id__in=ids).select_related('hilo').first()
        if previo:
            return previo.hilo
    base = normalizar_asunto(asunto)
    if base and base != (asunto or '').strip():  # "RE: x" sin cabeceras: mismo asunto reciente
        reciente = (
            Hilo.objects.filter(cuenta=cuenta, asunto__iexact=base, ultimo_mensaje_en__gte=fecha - timedelta(days=30))
            .order_by('-ultimo_mensaje_en').first()
        )
        if reciente:
            return reciente
    return Hilo.objects.create(cuenta=cuenta, asunto=base or asunto or '', ultimo_mensaje_en=fecha)


def registrar_evento(hilo, tipo, usuario=None, mensaje=None, **detalle):
    return EventoMensaje.objects.create(hilo=hilo, tipo=tipo, usuario=usuario, mensaje=mensaje, detalle=detalle)


def _actualizar_participantes(hilo, mensaje):
    personas = [{'correo': mensaje.de, 'nombre': mensaje.de_nombre}] + list(mensaje.para) + list(mensaje.cc)
    propios = set(hilo.cuenta.__class__.objects.values_list('direccion', flat=True))
    for p in personas:
        if p.get('correo') and p['correo'].lower() not in propios:
            hilo.participantes.add(contacto_para(p['correo'], p.get('nombre', '')))


def preparar_cuerpo(*, html='', texto=''):
    """(html sanitizado, texto plano, vista previa) a partir de lo que haya."""
    limpio = sanitizar_html(html) if html else texto_a_html(texto)
    plano = texto or html_a_texto(limpio)
    return limpio, plano, vista_previa(plano)


@transaction.atomic
def crear_mensaje(cuenta, tipo_carpeta, *, de, de_nombre='', para=(), cc=(), cco=(), asunto='',
                  html='', texto='', fecha=None, leido=False, message_id='', in_reply_to='',
                  references='', estado=Mensaje.RECIBIDO, creado_por=None, adjuntos=(), eml=None,
                  hilo=None, carpeta_obj=None):
    """Crea un Mensaje completo. `adjuntos`: [(nombre, mime, bytes, content_id, incrustado)]."""
    fecha = fecha or timezone.now()
    limpio, plano, previa = preparar_cuerpo(html=html, texto=texto)
    hilo = hilo or hilo_para(cuenta, asunto=asunto, fecha=fecha, in_reply_to=in_reply_to, references=references)
    mensaje = Mensaje(
        cuenta=cuenta, carpeta=carpeta_obj or carpeta(cuenta, tipo_carpeta), hilo=hilo,
        message_id=message_id or nuevo_message_id(cuenta), in_reply_to=in_reply_to, references=references,
        de=de.lower(), de_nombre=de_nombre, para=list(para), cc=list(cc), cco=list(cco), asunto=asunto,
        cuerpo_texto=plano, cuerpo_html=limpio, vista_previa=previa, fecha=fecha, leido=leido,
        estado_envio=estado, creado_por=creado_por,
    )
    if eml is not None:
        mensaje.eml_sha256 = hashlib.sha256(eml).hexdigest()
        mensaje.tamano = len(eml)
        mensaje.eml.save('original.eml', ContentFile(eml), save=False)
    mensaje.save()
    for nombre, mime, contenido, content_id, incrustado in adjuntos:
        agregar_adjunto(mensaje, nombre, mime, contenido, content_id=content_id, incrustado=incrustado)
    if fecha > hilo.ultimo_mensaje_en or hilo.mensajes.count() == 1:
        Hilo.objects.filter(pk=hilo.pk).update(ultimo_mensaje_en=fecha)
    _actualizar_participantes(hilo, mensaje)
    indexar(mensaje)
    return mensaje


def agregar_adjunto(mensaje, nombre, mime, contenido, *, content_id='', incrustado=False):
    adjunto = Adjunto(
        mensaje=mensaje, nombre=nombre[:255], tipo_mime=mime or 'application/octet-stream',
        tamano=len(contenido), sha256=hashlib.sha256(contenido).hexdigest(),
        content_id=content_id, incrustado=incrustado,
    )
    adjunto.archivo.save(nombre, ContentFile(contenido), save=False)
    adjunto.save()
    if not incrustado and not mensaje.tiene_adjuntos:
        Mensaje.objects.filter(pk=mensaje.pk).update(tiene_adjuntos=True)
        mensaje.tiene_adjuntos = True
    return adjunto


def actualizar_tiene_adjuntos(mensaje):
    tiene = mensaje.adjuntos.filter(incrustado=False).exists()
    Mensaje.objects.filter(pk=mensaje.pk).update(tiene_adjuntos=tiene)
    mensaje.tiene_adjuntos = tiene


def mover(mensajes, destino, usuario, tipo_evento=EventoMensaje.MOVIO):
    """Mueve mensajes (de la misma cuenta que `destino`) y deja un evento por hilo."""
    hilos = {}
    for m in mensajes:
        if m.cuenta_id != destino.cuenta_id or m.carpeta_id == destino.pk:
            continue
        hilos.setdefault(m.hilo_id, (m.hilo, m))
        Mensaje.objects.filter(pk=m.pk).update(carpeta=destino)
    for hilo, m in hilos.values():
        registrar_evento(hilo, tipo_evento, usuario, m, carpeta=destino.nombre)
    return len(hilos)
