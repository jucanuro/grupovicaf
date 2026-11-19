"""Entradas HTTP del correo real (Pasos 4 y 5). Viven en el host del correo.

- `cloudflare_entrante` (Paso 4): el Email Worker de Cloudflare entrega aquí
  cada correo recibido (el .eml crudo en el cuerpo) firmado con HMAC-SHA256.
- `ses_eventos` (Paso 5): Amazon SES, vía SNS, avisa rebotes y quejas.

Ninguna usa sesión ni CSRF: se autentican con un secreto compartido que solo
vive en el .env del servidor y en el Worker (nunca en el repositorio).
"""
import hashlib
import hmac
import json
import logging
import re
import time
import urllib.request
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import CuentaCorreo

logger = logging.getLogger(__name__)


def firma_entrante(secreto, fecha, para, cuerpo):
    """HMAC-SHA256 (hex) de «fecha \\n para \\n cuerpo». Lo calcula igual el Worker."""
    mensaje = f'{fecha}\n{para}\n'.encode() + cuerpo
    return hmac.new(secreto.encode(), mensaje, hashlib.sha256).hexdigest()


def _json(codigo, error):
    return JsonResponse({'error': error}, status=codigo)


@csrf_exempt
@require_POST
def cloudflare_entrante(request):
    secreto = settings.CORREO_WEBHOOK_SECRET
    if not secreto:
        return _json(503, 'webhook_sin_configurar')
    fecha = request.headers.get('X-Vicaf-Fecha', '')
    para = request.headers.get('X-Vicaf-Para', '').strip().lower()
    firma = request.headers.get('X-Vicaf-Firma', '')
    try:
        antiguedad = abs(time.time() - int(fecha))
    except ValueError:
        return _json(401, 'firma_invalida')
    if antiguedad > settings.CORREO_WEBHOOK_TOLERANCIA:
        return _json(401, 'firma_vencida')

    limite = settings.CORREO_MAX_ENTRANTE_BYTES
    try:
        largo = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        largo = 0
    if largo > limite:
        return _json(413, 'demasiado_grande')
    cuerpo = request.read(limite + 1)  # request.body toparía con DATA_UPLOAD_MAX_MEMORY_SIZE
    if len(cuerpo) > limite:
        return _json(413, 'demasiado_grande')

    esperada = firma_entrante(secreto, fecha, para, cuerpo)
    if not hmac.compare_digest(esperada, firma):
        return _json(401, 'firma_invalida')
    if not cuerpo:
        return _json(400, 'vacio')
    local, _, dominio = para.rpartition('@')
    para = f'{local}@{settings.CORREO_ENTRADA_ALIAS.get(dominio, dominio)}'
    # Se rechaza en el SMTP (el Worker hace setReject) lo que no tiene dueño.
    if not CuentaCorreo.objects.filter(activa=True, direccion=para).exists():
        return _json(404, 'destinatario_desconocido')

    from .tasks import recibir_entrante

    sha = hashlib.sha256(cuerpo).hexdigest()
    clave = guardar_entrante(sha, cuerpo)
    recibir_entrante.delay(clave, para)
    return JsonResponse({'ok': True, 'sha256': sha}, status=202)


def guardar_entrante(sha, cuerpo):
    """Deja el .eml en el almacén privado hasta que la tarea lo procese."""
    from django.core.files.base import ContentFile

    from .almacen import almacen_correo

    clave = f'entrantes/{sha}.eml'
    if not almacen_correo.exists(clave):
        almacen_correo.save(clave, ContentFile(cuerpo))
    return clave


# ---------------------------------------------------------------- Amazon SES / SNS

SNS_HOST = re.compile(r'^sns\.[a-z0-9-]+\.amazonaws\.com(\.cn)?$')


def _confirmar_suscripcion(url):
    anfitrion = urlparse(url)
    if anfitrion.scheme != 'https' or not SNS_HOST.match(anfitrion.hostname or ''):
        logger.warning('SubscribeURL de SNS descartada: %s', url[:120])
        return False
    try:
        with urllib.request.urlopen(url, timeout=10) as respuesta:  # noqa: S310 (host validado arriba)
            return 200 <= respuesta.status < 300
    except OSError as error:
        logger.warning('No se pudo confirmar la suscripción SNS: %s', error)
        return False


@csrf_exempt
@require_POST
def ses_eventos(request, token):
    esperado = settings.CORREO_SES_TOKEN
    if not esperado or not hmac.compare_digest(esperado, token):
        return HttpResponse(status=404)
    try:
        sobre = json.loads(request.read(1024 * 1024) or b'{}')
    except ValueError:
        return HttpResponse(status=400)
    tipo = sobre.get('Type')
    topico = settings.CORREO_SES_TOPIC_ARN
    if topico and sobre.get('TopicArn') != topico:
        return HttpResponse(status=403)
    if tipo == 'SubscriptionConfirmation':
        return HttpResponse(status=200 if _confirmar_suscripcion(sobre.get('SubscribeURL', '')) else 502)
    if tipo != 'Notification':
        return HttpResponse(status=204)
    try:
        evento = json.loads(sobre.get('Message') or '{}')
    except ValueError:
        return HttpResponse(status=400)
    from .tasks import procesar_evento_ses

    procesar_evento_ses.delay(evento)
    return HttpResponse(status=204)
