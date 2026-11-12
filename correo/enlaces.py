"""Paso de sesión entre laboratorio.<dominio> y email.<dominio>.

Las cookies de sesión NO se comparten entre subdominios (CLAUDE.md regla 5):
la sesión del LIMS nunca viaja a www ni a los subdominios que aún sirve
cPanel. Para no pedir un segundo login, el LIMS emite un enlace firmado:

- firmado con SECRET_KEY y un salt propio (django.core.signing);
- vence a los CORREO_ENLACE_SEGUNDOS (60 s por defecto);
- es de un solo uso: su nonce se marca en el cache (Redis) al consumirse;
- solo lleva a una ruta interna del host de correo.
"""
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.http.request import split_domain_port
from django.utils.http import url_has_allowed_host_and_scheme

SALT = 'correo.enlace-sesion'


def destino_seguro(valor):
    """Solo rutas internas ('/algo'); cualquier otra cosa vuelve a '/'."""
    if (
        isinstance(valor, str)
        and valor.startswith('/')
        and not valor.startswith('//')
        and '\\' not in valor
        and url_has_allowed_host_and_scheme(valor, allowed_hosts=None)
    ):
        return valor
    return '/'


def crear_enlace(user, destino='/'):
    datos = {'u': user.pk, 'n': secrets.token_urlsafe(16), 'd': destino_seguro(destino)}
    return signing.dumps(datos, salt=SALT)


def consumir_enlace(token):
    """Datos del enlace si es válido, vigente y no usado; si no, None."""
    vigencia = settings.CORREO_ENLACE_SEGUNDOS
    try:
        datos = signing.loads(token or '', salt=SALT, max_age=vigencia)
    except signing.BadSignature:  # incluye SignatureExpired
        return None
    # cache.add es atómico: solo el primer uso del nonce lo consigue.
    if not cache.add(f'correo:enlace:{datos["n"]}', 1, timeout=vigencia * 2):
        return None
    datos['d'] = destino_seguro(datos.get('d'))
    return datos


def _base(request, base_configurada, host):
    if base_configurada:
        return base_configurada
    _, puerto = split_domain_port(request.get_host())
    return f'{request.scheme}://{host}' + (f':{puerto}' if puerto else '')


def url_correo(request, ruta='/', **query):
    url = _base(request, settings.CORREO_BASE_URL, settings.CORREO_HOST) + ruta
    return url + ('?' + urlencode(query) if query else '')


def url_lab(request, ruta='/', **query):
    url = _base(request, settings.LAB_BASE_URL, settings.LAB_HOST) + ruta
    return url + ('?' + urlencode(query) if query else '')


# --- Descarga de adjuntos con enlace firmado de corta duración ---
# En el Paso 3 la vista `adjunto` redirige a la URL prefirmada de R2 con la
# misma vigencia; las plantillas no cambian.
SALT_ADJUNTO = 'correo.adjunto'


def token_adjunto(adjunto):
    return signing.dumps({'a': adjunto.pk}, salt=SALT_ADJUNTO)


def adjunto_de_token(token):
    try:
        datos = signing.loads(token or '', salt=SALT_ADJUNTO, max_age=settings.CORREO_URL_FIRMADA_SEGUNDOS)
    except signing.BadSignature:
        return None
    return datos.get('a')


def url_adjunto(adjunto):
    from django.urls import reverse
    return reverse('adjunto', urlconf='grupovicaf.urls_correo', args=[token_adjunto(adjunto)])
