"""Recepción de correo real: un .eml (RFC 5322) entra a la cuenta VICAF destinataria.

La usan:
- `python manage.py recibir_eml archivo.eml` (p. ej. un correo exportado de cPanel/Outlook);
- el puente de Mailpit en desarrollo (`correo.mailpit`);
- en el Paso 4, el webhook de Cloudflare Email Routing (mismo método `recibir`).

Reglas:
- un Mensaje por cada cuenta VICAF activa entre los destinatarios (Para, CC,
  Delivered-To, X-Original-To y los RCPT TO del sobre);
- idempotente: el mismo .eml (sha256) o el mismo Message-ID no entra dos veces
  en la misma cuenta;
- el HTML se sanitiza en `crear_mensaje` (nh3); los scripts nunca se guardan;
- las imágenes con Content-ID quedan como incrustadas (cid:) y el resto como adjuntos.
"""
import hashlib
import logging
import mimetypes
from datetime import timezone as dt_timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .mensajeria import crear_mensaje
from .models import CuentaCorreo, Mensaje
from .servicios import ServicioRecepcion

logger = logging.getLogger(__name__)


class CorreoRechazado(Exception):
    """El .eml no se puede recibir (demasiado grande, sin cuenta VICAF destinataria…)."""


def _texto(valor):
    try:
        return str(valor or '').strip()
    except Exception:  # cabecera mal codificada: se conserva lo legible
        return ''


def _personas(*valores):
    vistos, resultado = set(), []
    for nombre, correo in getaddresses([_texto(v) for v in valores if v]):
        correo = (correo or '').strip().lower()
        if '@' in correo and correo not in vistos:
            vistos.add(correo)
            resultado.append({'nombre': (nombre or '').strip(), 'correo': correo})
    return resultado


def _fecha(msg):
    try:
        fecha = msg['Date'].datetime if msg['Date'] is not None else None
    except Exception:
        fecha = None
    if fecha is None:
        return timezone.now()
    if timezone.is_naive(fecha):
        fecha = fecha.replace(tzinfo=dt_timezone.utc)
    # Un remitente con el reloj adelantado no debe quedar siempre arriba.
    return min(fecha, timezone.now())


def _es_spam(msg):
    bandera = _texto(msg.get('X-Spam-Flag')).lower()
    estado = _texto(msg.get('X-Spam-Status')).lower()
    return bandera == 'yes' or estado.startswith('yes')


def _suplanta_dominio(msg, remitente):
    """True si dice venir de nuestro dominio pero no lo respalda ninguna firma.

    Lo legítimo de @grupovicaf.com sale por SES y trae DKIM (d=grupovicaf.com o
    amazonses.com). Un estafador que escribe «De: algo@grupovicaf.com» no la tiene.
    También cuenta un SPF/DKIM/DMARC fallido declarado en Authentication-Results.
    Solo actúa con CORREO_FILTRAR_SUPLANTACION=True (en dev no hay DKIM).
    """
    if not getattr(settings, 'CORREO_FILTRAR_SUPLANTACION', False):
        return False
    dominio = remitente['correo'].rpartition('@')[2]
    if dominio not in settings.CORREO_DOMINIOS:
        return False
    resultados = ' '.join(_texto(v).lower() for v in (msg.get_all('Authentication-Results') or []))
    resultados += ' ' + _texto(msg.get('Received-SPF')).lower()
    if any(f'{m}={r}' in resultados for m in ('spf', 'dkim', 'dmarc') for r in ('fail', 'softfail', 'none')):
        return True
    firmas = ' '.join(_texto(v).lower().replace(' ', '') for v in (msg.get_all('DKIM-Signature') or []))
    respaldado = any(f'd={d}' in firmas for d in (*settings.CORREO_DOMINIOS, 'amazonses.com'))
    return not respaldado


def _cuerpo_y_adjuntos(msg):
    """(html, texto, [(nombre, mime, bytes, content_id, incrustado)])."""
    parte_html = msg.get_body(preferencelist=('html',))
    parte_texto = msg.get_body(preferencelist=('plain',))
    html = texto = ''
    try:
        html = parte_html.get_content() if parte_html is not None else ''
    except Exception:
        html = ''
    try:
        texto = parte_texto.get_content() if parte_texto is not None else ''
    except Exception:
        texto = ''
    cuerpos = {id(p) for p in (parte_html, parte_texto) if p is not None}

    adjuntos = []
    for n, parte in enumerate(msg.walk(), start=1):
        if parte.is_multipart() or id(parte) in cuerpos:
            continue
        contenido = parte.get_payload(decode=True)
        if contenido is None:
            continue
        mime = parte.get_content_type()
        disposicion = parte.get_content_disposition()
        content_id = _texto(parte.get('Content-ID')).strip('<>')
        nombre = parte.get_filename()
        if not nombre:
            extension = mimetypes.guess_extension(mime) or '.bin'
            nombre = f'adjunto-{n}{extension}'
        incrustado = bool(content_id) and mime.startswith('image/') and disposicion != 'attachment'
        adjuntos.append((nombre, mime, contenido, content_id, incrustado))
    return html, texto, adjuntos


class RecepcionEML(ServicioRecepcion):
    def recibir(self, crudo: bytes, destinatarios=()):
        if not crudo:
            raise CorreoRechazado('El correo está vacío.')
        if len(crudo) > settings.CORREO_MAX_ENTRANTE_BYTES:
            raise CorreoRechazado('El correo supera el tamaño máximo permitido.')
        msg = BytesParser(policy=policy.default).parsebytes(crudo)

        para = _personas(msg.get('To'))
        cc = _personas(msg.get('Cc'))
        sobre = _personas(msg.get('Delivered-To'), msg.get('X-Original-To'), ', '.join(destinatarios or ()))
        direcciones = {p['correo'] for p in para + cc + sobre}
        cuentas = list(CuentaCorreo.objects.filter(activa=True, direccion__in=direcciones))
        if not cuentas:
            raise CorreoRechazado('Ningún destinatario es una cuenta de correo VICAF activa.')

        remitente = (_personas(msg.get('From')) or [{'nombre': '', 'correo': 'desconocido@desconocido.invalid'}])[0]
        message_id = _texto(msg.get('Message-ID'))
        html, texto, adjuntos = _cuerpo_y_adjuntos(msg)
        fecha = _fecha(msg)
        suplantado = _suplanta_dominio(msg, remitente)
        carpeta = 'spam' if (suplantado or _es_spam(msg)) else 'entrada'
        asunto = _texto(msg.get('Subject'))[:500]
        if suplantado:
            logger.warning('Posible suplantación de %s: va a No deseado.', remitente['correo'])
            asunto = f'[POSIBLE SUPLANTACIÓN] {asunto}'[:500]

        sha = hashlib.sha256(crudo).hexdigest()
        creados = []
        for cuenta in cuentas:
            repetido = Mensaje.objects.filter(cuenta=cuenta, eml_sha256=sha)
            if message_id:
                repetido = repetido | Mensaje.objects.filter(cuenta=cuenta, message_id=message_id)
            if repetido.exists():
                logger.info('Correo repetido en %s (%s): se ignora.', cuenta.direccion, message_id or sha[:12])
                continue
            with transaction.atomic():
                creados.append(crear_mensaje(
                    cuenta, carpeta,
                    de=remitente['correo'], de_nombre=remitente['nombre'], para=para, cc=cc,
                    asunto=asunto, html=html, texto=texto if not html else '',
                    fecha=fecha, message_id=message_id[:998],
                    in_reply_to=_texto(msg.get('In-Reply-To'))[:998], references=_texto(msg.get('References')),
                    adjuntos=adjuntos, eml=crudo,
                ))
        return creados


def recepcion():
    """Implementación activa de ServicioRecepcion."""
    return RecepcionEML()
