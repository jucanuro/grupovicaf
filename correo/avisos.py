"""Avisos del correo (campanita): no leídos, pendientes y mensajes llegados desde la última consulta.

Solo cuentas a las que el usuario tiene acceso (cuentas_de); no cuenta «No deseado».
"""
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone

from .models import Asignacion, Carpeta, Mensaje
from .cuentas import cuentas_de

MAX_NUEVOS = 5
MAX_LISTA = 5


def _url_hilo(m):
    """Abre el hilo en el panel de lectura de su carpeta, como un clic en la lista."""
    return reverse('carpeta', args=[m.cuenta.slug, m.carpeta_id]) + f'?h={m.hilo_id}'


def _fila(m, url=None):
    return {
        'id': m.pk, 'cuenta': m.cuenta.nombre, 'de': m.de_nombre or m.de,
        'asunto': m.asunto or '(sin asunto)',
        'fecha': timezone.localtime(m.fecha).isoformat(),
        'url': url or _url_hilo(m),
    }


def _fila_borrador(m):
    fila = _fila(m, reverse('borrador', args=[m.pk]))
    destino = next((d.get('nombre') or d.get('correo') for d in m.para if isinstance(d, dict)), '')
    fila['de'] = f'Para: {destino}' if destino else 'Sin destinatario'
    return fila


def _pendientes(user, cuentas):
    """Lo que espera acción de `user`: hilos asignados, envíos fallidos y sus borradores."""
    asignaciones = (
        Asignacion.objects.filter(asignado_a=user, estado=Asignacion.PENDIENTE, hilo__cuenta__in=cuentas)
        .select_related('hilo')
        .order_by('-hilo__ultimo_mensaje_en')
    )
    asignados = []
    for a in asignaciones[:MAX_LISTA]:
        m = (a.hilo.mensajes.exclude(estado_envio=Mensaje.BORRADOR)
             .select_related('cuenta').order_by('-fecha').first())
        if m is not None:
            asignados.append(_fila(m))
    propios = Mensaje.objects.filter(cuenta__in=cuentas).select_related('cuenta')
    fallidos = propios.filter(estado_envio=Mensaje.FALLIDO).order_by('-fecha')
    en_cola = propios.filter(estado_envio=Mensaje.EN_COLA)
    borradores = propios.filter(estado_envio=Mensaje.BORRADOR, creado_por=user).order_by('-actualizado_en')
    return {
        'asignados': {'n': asignaciones.count(), 'lista': asignados},
        'fallidos': {'n': fallidos.count(), 'lista': [_fila(m) for m in fallidos[:MAX_LISTA]]},
        'en_cola': en_cola.count(),
        'borradores': {
            'n': borradores.count(),
            'lista': [_fila_borrador(m) for m in borradores[:MAX_LISTA]],
        },
    }


def resumen_avisos(user, desde=None):
    """{total, ultimo, cuentas: {slug: n}, nuevos: [...], por_cuenta, sin_leer, pendientes}.

    `desde` = id del último mensaje que el navegador ya conocía. Sin `desde`
    (primera consulta) no hay `nuevos`: solo se fija la referencia, para no
    avisar de lo que ya estaba en la bandeja al abrir la página.
    """
    cuentas = list(cuentas_de(user))
    entrada = Mensaje.objects.filter(cuenta__in=cuentas, carpeta__tipo=Carpeta.ENTRADA)
    ultimo = entrada.aggregate(m=Max('pk'))['m'] or 0
    nuevos = []
    if desde is not None:
        for m in (entrada.filter(pk__gt=desde, leido=False).select_related('cuenta').order_by('pk')[:MAX_NUEVOS]):
            nuevos.append({
                'id': m.pk, 'cuenta': m.cuenta.nombre, 'de': m.de_nombre or m.de,
                'asunto': m.asunto or '(sin asunto)',
            })
    sin_leer = entrada.filter(leido=False).select_related('cuenta').order_by('-fecha')[:MAX_LISTA]
    return {
        'total': sum(c.no_leidos for c in cuentas),
        'ultimo': ultimo,
        'cuentas': {c.slug: c.no_leidos for c in cuentas},
        'nuevos': nuevos,
        'por_cuenta': [
            {'slug': c.slug, 'nombre': c.nombre, 'no_leidos': c.no_leidos,
             'url': reverse('bandeja_cuenta', args=[c.slug])}
            for c in cuentas
        ],
        'sin_leer': [_fila(m) for m in sin_leer],
        'pendientes': _pendientes(user, cuentas),
    }
