"""Anti-spam para los formularios públicos de /contacto/: honeypot + rate limit por IP.

Sin captcha de terceros (cuestan conversión, ver encargo). El rate limit usa
el caché de Redis ya configurado en settings (CACHES['default']).
"""
from django.core.cache import cache

HONEYPOT_FIELD = 'sitio_web_empresa'

RATE_LIMIT_MAX_INTENTOS = 5
RATE_LIMIT_VENTANA_SEGUNDOS = 60 * 60


def es_honeypot(request):
    """True si el campo trampa (oculto por CSS, invisible para humanos) llegó relleno."""
    return bool(request.POST.get(HONEYPOT_FIELD, '').strip())


def obtener_ip_cliente(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def rate_limit_excedido(request, clave_formulario):
    """Cuenta este intento para esta IP + formulario (cache.add + incr: atómico en Redis).

    Devuelve True si con este intento ya se superó RATE_LIMIT_MAX_INTENTOS
    dentro de la ventana actual.
    """
    ip = obtener_ip_cliente(request) or 'sin-ip'
    clave = f'web_contacto:rate:{clave_formulario}:{ip}'

    cache.add(clave, 0, RATE_LIMIT_VENTANA_SEGUNDOS)
    intentos = cache.incr(clave)

    return intentos > RATE_LIMIT_MAX_INTENTOS
