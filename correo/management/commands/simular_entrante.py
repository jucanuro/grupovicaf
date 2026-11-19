"""Solo desarrollo: un "cliente" escribe a una cuenta VICAF.

    python manage.py simular_entrante
    python manage.py simular_entrante --para laboratorio@grupovicaf.com --de "Ana <ana@obra.pe>" \\
        --asunto "Consulta" --texto "Hola" --adjunto plano.pdf
    python manage.py simular_entrante --responder 42     # el cliente responde al correo 42

Con CORREO_ENVIO=smtp el correo pasa por el SMTP (Mailpit) y entra a la bandeja
por el puente de Mailpit, como llegaría de verdad. Sin SMTP (o con --directo)
entra directo por RecepcionEML.
"""
import mimetypes
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, getaddresses, make_msgid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from correo.models import CuentaCorreo, Mensaje
from correo.mensajeria import normalizar_asunto
from correo.recepcion import recepcion


class Command(BaseCommand):
    help = 'Simula un correo entrante de un cliente (solo DEBUG=True).'

    def add_arguments(self, parser):
        parser.add_argument('--para', default='', help='cuenta VICAF (por defecto la primera activa)')
        parser.add_argument('--de', default='Ana Quispe <ana.quispe@constructora-demo.pe>')
        parser.add_argument('--asunto', default='Solicitud de cotización: ensayo de compresión')
        parser.add_argument('--texto', default=(
            'Buenos días,\n\nNecesitamos cotizar el ensayo de resistencia a la compresión de 12 probetas '
            'de concreto. ¿Nos envían la propuesta?\n\nSaludos,\nAna Quispe'
        ))
        parser.add_argument('--adjunto', action='append', default=[], help='ruta de un archivo (repetible)')
        parser.add_argument('--responder', type=int, help='pk de un correo VICAF al que responde el cliente')
        parser.add_argument('--directo', action='store_true', help='no pasar por SMTP aunque esté configurado')

    def handle(self, *args, **o):
        if not settings.DEBUG:
            raise CommandError('simular_entrante es solo para desarrollo (DEBUG=True).')
        msg = EmailMessage()
        if o['responder']:
            original = Mensaje.objects.select_related('cuenta').filter(pk=o['responder']).first()
            if original is None:
                raise CommandError(f'No existe el correo {o["responder"]}.')
            cliente = (original.para or [{'nombre': '', 'correo': original.de}])[0]
            de = f'{cliente.get("nombre") or ""} <{cliente["correo"]}>'.strip()
            para = original.cuenta.direccion
            msg['Subject'] = f'RE: {normalizar_asunto(original.asunto)}'
            msg['In-Reply-To'] = original.message_id
            msg['References'] = f'{original.references} {original.message_id}'.strip()
            texto = o['texto'] if o['texto'] != self._defecto('texto') else (
                'Gracias por la información. Confirmamos y quedamos atentos.\n\nSaludos.')
        else:
            cuenta = (CuentaCorreo.objects.filter(activa=True, direccion=o['para'].lower()).first() if o['para']
                      else CuentaCorreo.objects.filter(activa=True).order_by('pk').first())
            if cuenta is None:
                raise CommandError('No hay esa cuenta VICAF activa. Corra antes seed_correo_demo.')
            de, para, texto = o['de'], cuenta.direccion, o['texto']
            msg['Subject'] = o['asunto']
        remitente = getaddresses([de])[0][1]
        msg['From'] = de
        msg['To'] = para
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid(domain=remitente.split('@')[-1] or 'cliente.invalid')
        msg.set_content(texto)
        parrafos = ''.join(f'<p>{p.replace(chr(10), "<br>")}</p>' for p in texto.split('\n\n'))
        msg.add_alternative(f'<html><body>{parrafos}</body></html>', subtype='html')
        for ruta in o['adjunto']:
            archivo = Path(ruta)
            if not archivo.is_file():
                raise CommandError(f'No existe el archivo {ruta}')
            tipo = (mimetypes.guess_type(archivo.name)[0] or 'application/octet-stream').split('/')
            msg.add_attachment(archivo.read_bytes(), tipo[0], tipo[1], filename=archivo.name)

        if settings.CORREO_ENVIO == 'smtp' and settings.CORREO_SMTP_HOST and not o['directo']:
            with smtplib.SMTP(settings.CORREO_SMTP_HOST, settings.CORREO_SMTP_PUERTO, timeout=30) as smtp:
                smtp.send_message(msg, from_addr=remitente, to_addrs=[para])
            espera = ' En unos segundos aparece en la bandeja.' if settings.CORREO_MAILPIT_URL else ''
            self.stdout.write(self.style.SUCCESS(f'Enviado por SMTP de {de} a {para}.{espera}'))
        else:
            creados = recepcion().recibir(msg.as_bytes(), destinatarios=[para])
            self.stdout.write(self.style.SUCCESS(f'Recibido en {para} ({len(creados)} correo).'))

    def _defecto(self, campo):
        return self.create_parser('manage.py', 'simular_entrante').get_default(campo)
