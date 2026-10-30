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
    """IP del visitante tal como la vio nginx, no la que el visitante declare.

    nginx fija X-Real-IP con $remote_addr (sobrescribe lo que mande el
    cliente) y añade $remote_addr al FINAL de X-Forwarded-For. La primera IP
    de X-Forwarded-For la escribe el propio visitante: usarla permitía
    saltarse el rate limit cambiando la cabecera en cada envío.
    """
    real_ip = request.META.get('HTTP_X_REAL_IP', '').strip()
    if real_ip:
        return real_ip
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[-1].strip()
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
