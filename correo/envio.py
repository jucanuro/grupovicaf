"""Envío real por SMTP: arma el MIME completo de un Mensaje y lo entrega.

En desarrollo el SMTP es Mailpit (docker-compose.dev.yml, http://localhost:8025
para ver lo que salió). En producción será la interfaz SMTP de Amazon SES
(Paso 5): solo cambian CORREO_SMTP_* en el .env, no este código.

El MIME lleva:
- texto plano + HTML (multipart/alternative);
- imágenes del cuerpo como multipart/related con su Content-ID (cid:);
- adjuntos;
- Message-ID, In-Reply-To y References, para que el cliente del destinatario
  arme el hilo y su respuesta vuelva al mismo hilo en VICAF.
"""
import smtplib
import socket
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from django.conf import settings
from django.utils import timezone

from .servicios import ResultadoEnvio, ServicioEnvio

ESTILO = "font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#0F172A"


def _direcciones(personas):
    return ', '.join(formataddr((p.get('nombre') or '', p['correo'])) for p in personas)


def _leer(adjunto):
    with adjunto.archivo.open('rb') as archivo:
        return archivo.read()


def construir_mime(mensaje):
    """EmailMessage listo para enviar (sin Bcc en las cabeceras)."""
    m = EmailMessage()
    m['From'] = formataddr((mensaje.de_nombre or '', mensaje.de))
    if mensaje.para:
        m['To'] = _direcciones(mensaje.para)
    if mensaje.cc:
        m['Cc'] = _direcciones(mensaje.cc)
    m['Subject'] = mensaje.asunto or ''
    m['Date'] = formatdate(timezone.localtime(mensaje.fecha).timestamp(), localtime=True)
    m['Message-ID'] = mensaje.message_id
    if mensaje.in_reply_to:
        m['In-Reply-To'] = mensaje.in_reply_to
    if mensaje.references:
        m['References'] = mensaje.references
    m['X-Mailer'] = 'Correo VICAF'

    m.set_content(mensaje.cuerpo_texto or ' ')
    html = (f'<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
            f'<body><div style="{ESTILO}">{mensaje.cuerpo_html}</div></body></html>')
    m.add_alternative(html, subtype='html')
    parte_html = m.get_payload()[-1]

    for adjunto in mensaje.adjuntos.all().order_by('pk'):
        principal, _, secundario = (adjunto.tipo_mime or 'application/octet-stream').partition('/')
        contenido = _leer(adjunto)
        if adjunto.incrustado and adjunto.content_id:
            parte_html.add_related(contenido, principal, secundario or 'octet-stream',
                                   cid=f'<{adjunto.content_id}>', filename=adjunto.nombre,
                                   disposition='inline')
        else:
            m.add_attachment(contenido, principal, secundario or 'octet-stream', filename=adjunto.nombre)
    return m


class ServicioEnvioSMTP(ServicioEnvio):
    def enviar(self, mensaje) -> ResultadoEnvio:
        destinos = [d['correo'] for d in list(mensaje.para) + list(mensaje.cc) + list(mensaje.cco)]
        if not destinos:
            return ResultadoEnvio(ok=False, error='El mensaje no tiene destinatarios.')
        if not settings.CORREO_SMTP_HOST:
            return ResultadoEnvio(ok=False, error='Falta CORREO_SMTP_HOST en el .env.', reintentar=True)
        mime = construir_mime(mensaje)
        try:
            with smtplib.SMTP(settings.CORREO_SMTP_HOST, settings.CORREO_SMTP_PUERTO, timeout=30) as smtp:
                if settings.CORREO_SMTP_TLS:
                    smtp.starttls()
                if settings.CORREO_SMTP_USUARIO:
                    smtp.login(settings.CORREO_SMTP_USUARIO, settings.CORREO_SMTP_CLAVE)
                rechazados = smtp.send_message(mime, from_addr=mensaje.de, to_addrs=destinos)
        except smtplib.SMTPRecipientsRefused as error:
            detalle = '; '.join(f'{d}: {c} {r.decode(errors="replace")}' for d, (c, r) in error.recipients.items())
            return ResultadoEnvio(ok=False, error=f'Destinatarios rechazados. {detalle}')
        except smtplib.SMTPResponseException as error:
            texto = error.smtp_error.decode(errors='replace') if isinstance(error.smtp_error, bytes) else error.smtp_error
            # 4xx: temporal (se reintenta); 5xx: definitivo.
            return ResultadoEnvio(ok=False, error=f'El servidor respondió {error.smtp_code}: {texto}',
                                  reintentar=400 <= error.smtp_code < 500)
        except (smtplib.SMTPException, OSError, socket.timeout) as error:
            return ResultadoEnvio(ok=False, error=f'No se pudo conectar con el servidor de correo: {error}',
                                  reintentar=True)
        if rechazados:
            detalle = ', '.join(rechazados)
            return ResultadoEnvio(ok=True, id_proveedor=mensaje.message_id, eml=mime.as_bytes(),
                                  error=f'No se entregó a: {detalle}')
        return ResultadoEnvio(ok=True, id_proveedor=mensaje.message_id, eml=mime.as_bytes())
