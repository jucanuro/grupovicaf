"""Enrutamiento por host: el mismo proceso 'lab' sirve el LIMS y el correo."""
from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.http.request import split_domain_port

URLCONF_CORREO = 'grupovicaf.urls_correo'

# El correo muestra contenido de terceros: política estricta. Sin scripts ni
# estilos en línea; fuentes de Google; imágenes propias o data:. El cuerpo de
# los correos (Paso 2) irá en un iframe sandbox con su propia CSP.
CSP_CORREO = '; '.join((
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
))


def es_host_correo(request):
    try:
        host, _ = split_domain_port(request.get_host())
    except DisallowedHost:
        return False  # CommonMiddleware responderá 400 más adelante
    return host.lower() == settings.CORREO_HOST.lower()


class CorreoHostMiddleware:
    """En el rol 'lab', las peticiones a CORREO_HOST usan urls_correo.py.

    Cualquier otro host (laboratorio., localhost, 127.0.0.1) sigue con el
    URLconf de siempre: el LIMS no cambia. En el rol 'web' no hace nada.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.es_host_correo = settings.SITE_ROLE == 'lab' and es_host_correo(request)
        if request.es_host_correo:
            request.urlconf = URLCONF_CORREO
        response = self.get_response(request)
        if request.es_host_correo:
            response.headers.setdefault('Content-Security-Policy', CSP_CORREO)
            response.headers.setdefault('Referrer-Policy', 'no-referrer')
        return response
