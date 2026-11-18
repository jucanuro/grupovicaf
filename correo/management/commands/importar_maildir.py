"""Importa un buzón Maildir (p. ej. copiado del cPanel) a una cuenta VICAF.

    python manage.py importar_maildir informes@grupovicaf.com /ruta/al/maildir
    python manage.py importar_maildir informes@grupovicaf.com /ruta/al/maildir --simular

El Maildir de cPanel es una carpeta con `cur/`, `new/` y subcarpetas `.Sent`,
`.Drafts`, `.Trash`, `.spam`, etc. Cada archivo es un correo completo. Se importa
con el mismo camino que la recepción real (HTML sanitizado, hilos, adjuntos).
Es idempotente: se puede repetir y no duplica (mismo sha256 o Message-ID).
Mantiene la fecha original, la carpeta y el estado leído; los correos de
«Enviados» quedan como enviados, no como recibidos.
"""
import hashlib
import time
from email import policy
from email.parser import BytesParser
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from correo.mensajeria import asegurar_carpetas, crear_mensaje
from correo.models import Carpeta, CuentaCorreo, Mensaje
from correo.recepcion import _cuerpo_y_adjuntos, _es_spam, _fecha, _personas, _texto

# nombre de subcarpeta Maildir (sin el punto, en minúsculas) -> tipo de carpeta
CARPETAS = {
    'inbox': Carpeta.ENTRADA,
    'sent': Carpeta.ENVIADOS, 'inbox.sent': Carpeta.ENVIADOS, 'sent items': Carpeta.ENVIADOS,
    'sent messages': Carpeta.ENVIADOS, 'enviados': Carpeta.ENVIADOS, 'elementos enviados': Carpeta.ENVIADOS,
    'drafts': Carpeta.BORRADORES, 'inbox.drafts': Carpeta.BORRADORES, 'borradores': Carpeta.BORRADORES,
    'trash': Carpeta.PAPELERA, 'inbox.trash': Carpeta.PAPELERA, 'papelera': Carpeta.PAPELERA,
    'deleted items': Carpeta.PAPELERA, 'elementos eliminados': Carpeta.PAPELERA,
    'spam': Carpeta.SPAM, 'junk': Carpeta.SPAM, 'inbox.spam': Carpeta.SPAM, 'inbox.junk': Carpeta.SPAM,
    'archive': Carpeta.ARCHIVADOS, 'archives': Carpeta.ARCHIVADOS, 'archivo': Carpeta.ARCHIVADOS,
}


def carpetas_del_maildir(raiz):
    """[(nombre_visible, ruta)] con la bandeja principal y cada subcarpeta que tenga cur/new."""
    encontradas = []
    if (raiz / 'cur').is_dir() or (raiz / 'new').is_dir():
        encontradas.append(('INBOX', raiz))
    for sub in sorted(raiz.iterdir()):
        if sub.is_dir() and sub.name.startswith('.') and ((sub / 'cur').is_dir() or (sub / 'new').is_dir()):
            encontradas.append((sub.name[1:], sub))
    return encontradas


def archivos_de(carpeta):
    for sub in ('cur', 'new'):
        ruta = carpeta / sub
        if ruta.is_dir():
            for archivo in sorted(ruta.iterdir()):
                if archivo.is_file() and not archivo.name.startswith('.'):
                    yield archivo, sub == 'new'


def leido_por_bandera(archivo, es_new):
    if es_new:
        return False
    _, _, banderas = archivo.name.partition(':2,')
    return 'S' in banderas


class Command(BaseCommand):
    help = 'Importa un buzón Maildir a una cuenta VICAF (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('cuenta', help='dirección de la cuenta VICAF, p. ej. informes@grupovicaf.com')
        parser.add_argument('maildir', help='carpeta raíz del Maildir')
        parser.add_argument('--simular', action='store_true', help='solo cuenta, no guarda nada')
        parser.add_argument('--limite', type=int, default=0, help='máximo de correos (para pruebas)')

    def handle(self, *args, **opciones):
        cuenta = CuentaCorreo.objects.filter(direccion=opciones['cuenta'].lower()).first()
        if cuenta is None:
            raise CommandError(f'No existe la cuenta {opciones["cuenta"]}. Créala en /administrar/.')
        raiz = Path(opciones['maildir'])
        if not raiz.is_dir():
            raise CommandError(f'No existe la carpeta {raiz}')
        simular, limite = opciones['simular'], opciones['limite']
        if not simular:
            asegurar_carpetas(cuenta)

        nuevos = repetidos = errores = 0
        inicio = time.time()
        for nombre, ruta in carpetas_del_maildir(raiz):
            tipo = CARPETAS.get(nombre.lower())
            personal = None
            if tipo is None:
                tipo, personal = Carpeta.PERSONAL, nombre.replace('INBOX.', '').replace('.', ' / ')
            total = sum(1 for _ in archivos_de(ruta))
            self.stdout.write(f'Carpeta {nombre} -> {personal or tipo}: {total} archivos')
            if simular:
                nuevos += total
                continue
            carpeta_obj = None
            if personal:
                carpeta_obj, _ = Carpeta.objects.get_or_create(cuenta=cuenta, tipo=Carpeta.PERSONAL, nombre=personal[:80])
            for n, (archivo, es_new) in enumerate(archivos_de(ruta), 1):
                if limite and nuevos >= limite:
                    break
                try:
                    resultado = self.importar(cuenta, archivo, tipo, carpeta_obj, leido_por_bandera(archivo, es_new))
                except Exception as error:  # un correo roto no detiene el resto
                    errores += 1
                    self.stderr.write(f'{archivo.name}: {error}')
                    continue
                if resultado:
                    nuevos += 1
                else:
                    repetidos += 1
                if n % 200 == 0:
                    self.stdout.write(f'  {n}/{total} ({int(time.time() - inicio)} s)')
        self.stdout.write(self.style.SUCCESS(
            f'{cuenta.direccion}: {nuevos} {"por importar" if simular else "nuevos"}, '
            f'{repetidos} ya estaban, {errores} con error ({int(time.time() - inicio)} s)'))

    def importar(self, cuenta, archivo, tipo, carpeta_obj, leido):
        crudo = archivo.read_bytes()
        if not crudo or len(crudo) > settings.CORREO_MAX_ENTRANTE_BYTES:
            raise ValueError('vacío o demasiado grande')
        msg = BytesParser(policy=policy.default).parsebytes(crudo)
        message_id = _texto(msg.get('Message-ID'))[:998]
        sha = hashlib.sha256(crudo).hexdigest()
        repetido = Mensaje.objects.filter(cuenta=cuenta, eml_sha256=sha)
        if message_id:
            repetido = repetido | Mensaje.objects.filter(cuenta=cuenta, message_id=message_id)
        if repetido.exists():
            return False
        remitente = (_personas(msg.get('From')) or [{'nombre': '', 'correo': 'desconocido@desconocido.invalid'}])[0]
        html, texto, adjuntos = _cuerpo_y_adjuntos(msg)
        if tipo == Carpeta.ENTRADA and _es_spam(msg):
            tipo = Carpeta.SPAM
        saliente = tipo in (Carpeta.ENVIADOS, Carpeta.BORRADORES)
        estado = Mensaje.RECIBIDO
        if tipo == Carpeta.ENVIADOS:
            estado = Mensaje.ENVIADO
        elif tipo == Carpeta.BORRADORES:
            estado = Mensaje.BORRADOR
        crear_mensaje(
            cuenta, tipo, carpeta_obj=carpeta_obj,
            de=remitente['correo'], de_nombre=remitente['nombre'],
            para=_personas(msg.get('To')), cc=_personas(msg.get('Cc')),
            asunto=_texto(msg.get('Subject'))[:500], html=html, texto=texto if not html else '',
            fecha=_fecha(msg), leido=True if saliente else leido, message_id=message_id,
            in_reply_to=_texto(msg.get('In-Reply-To'))[:998], references=_texto(msg.get('References')),
            estado=estado, adjuntos=adjuntos, eml=crudo,
        )
        return True
