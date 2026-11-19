"""Avisos de correo nuevo: contador de no leídos y mensajes llegados desde la última consulta.

Solo cuentas a las que el usuario tiene acceso (cuentas_de); no cuenta «No deseado».
"""
from django.db.models import Max

from .cuentas import cuentas_de
from .models import Mensaje

MAX_NUEVOS = 5


def resumen_avisos(user, desde=None):
    """{total, ultimo, cuentas: {slug: n}, nuevos: [...]}.

    `desde` = id del último mensaje que el navegador ya conocía. Sin `desde`
    (primera consulta) no hay `nuevos`: solo se fija la referencia, para no
    avisar de lo que ya estaba en la bandeja al abrir la página.
    """
    cuentas = list(cuentas_de(user))
    entrada = Mensaje.objects.filter(cuenta__in=cuentas, carpeta__tipo='entrada')
    ultimo = entrada.aggregate(m=Max('pk'))['m'] or 0
    nuevos = []
    if desde is not None:
        for m in (entrada.filter(pk__gt=desde, leido=False).select_related('cuenta').order_by('pk')[:MAX_NUEVOS]):
            nuevos.append({
                'id': m.pk, 'cuenta': m.cuenta.nombre, 'de': m.de_nombre or m.de,
                'asunto': m.asunto or '(sin asunto)',
            })
    return {
        'total': sum(c.no_leidos for c in cuentas),
        'ultimo': ultimo,
        'cuentas': {c.slug: c.no_leidos for c in cuentas},
        'nuevos': nuevos,
    }
