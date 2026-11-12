"""Puente de desarrollo: Mailpit -> bandejas VICAF.

En local no hay MX ni Cloudflare. Mailpit (docker-compose.dev.yml) recibe todo
lo que se envía por SMTP: lo que sale de VICAF hacia clientes y lo que un
"cliente" de prueba manda a informes@grupovicaf.com. Cada 15 s (beat) este
puente baja de la API de Mailpit los correos dirigidos a una cuenta VICAF activa
y los pasa por `RecepcionEML`, igual que hará el webhook de Cloudflare.

No se usa en producción (CORREO_MAILPIT_URL vacío).
"""
import json
import logging
import urllib.request

from django.core.cache import cache

from .models import CuentaCorreo
from .recepcion import CorreoRechazado, recepcion

logger = logging.getLogger(__name__)
VISTO = 'correo:mailpit:visto:{}'
LIMITE = 200


def _pedir(url):
    with urllib.request.urlopen(url, timeout=10) as respuesta:  # noqa: S310 (URL de configuración, solo dev)
        return respuesta.read()


def traer(base_url):
    """Devuelve cuántos mensajes nuevos entraron a las bandejas."""
    propias = set(CuentaCorreo.objects.filter(activa=True).values_list('direccion', flat=True))
    if not propias:
        return 0
    try:
        lista = json.loads(_pedir(f'{base_url}/api/v1/messages?limit={LIMITE}'))
    except (OSError, ValueError) as error:
        logger.warning('No se pudo leer Mailpit en %s: %s', base_url, error)
        return 0
    nuevos = 0
    for resumen in lista.get('messages') or []:
        clave = VISTO.format(resumen.get('ID'))
        if cache.get(clave):
            continue
        destinatarios = [
            (p.get('Address') or '').lower()
            for campo in ('To', 'Cc', 'Bcc') for p in (resumen.get(campo) or [])
        ]
        para_vicaf = [d for d in destinatarios if d in propias]
        if para_vicaf:
            try:
                crudo = _pedir(f'{base_url}/api/v1/message/{resumen["ID"]}/raw')
                nuevos += len(recepcion().recibir(crudo, destinatarios=para_vicaf))
            except CorreoRechazado as error:
                logger.info('Mailpit %s no se recibió: %s', resumen.get('ID'), error)
            except OSError as error:
                logger.warning('No se pudo bajar %s de Mailpit: %s', resumen.get('ID'), error)
                continue  # se reintenta en la próxima pasada
        cache.set(clave, True, 60 * 60 * 24 * 30)
    return nuevos
