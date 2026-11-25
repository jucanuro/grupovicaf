"""Programa de ensayos del día (HU-LIMS-21, REQ-LIMS-62 a 71).

El supervisor de ensayos no entrega «una solicitud por recepción»: entrega al
personal una hoja **por cliente y por día** con todas las probetas que toca
romper ese día, sin importar su edad (las de 7, 14 y 28 días de vaciados
distintos van juntas). Este módulo arma esa hoja a partir de las líneas de
compresión ya asignadas (`DetalleSolicitudEnsayo`), sin cambiar el modelo:
cada probeta sigue perteneciendo a su solicitud y a su informe.

Fecha prevista de ensayo de una probeta (RN-12):

1. fecha de moldeo + edad de ensayo solicitada (datos FOR-004 de la probeta);
2. si falta alguna, la «fecha de ensayo programada» de su recepción;
3. si falta también, la probeta queda «sin fecha» y se avisa.

Una probeta ya terminada aparece el día en que se ensayó de verdad
(`ResultadoEnsayo.fecha_ensayo`), aunque su fecha prevista fuera otra.
Las pendientes con fecha prevista anterior a hoy se listan como «atrasadas» en
el programa de hoy (RN-13).
"""
from collections import OrderedDict
from datetime import date, timedelta

from django.db.models import Count, Q

from trabajadores.permissions import ve_todos_los_ensayos

from .models import DetalleSolicitudEnsayo, ResultadoEnsayo

ESTADO_POR_MEDIR = 'por_medir'
ESTADO_MEDIDA = 'medida'
ESTADO_EN_REGISTRO = 'en_registro'
ESTADO_TERMINADA = 'terminada'
ESTADO_DEVUELTA = 'devuelta'

ESTADOS = {
    ESTADO_POR_MEDIR: ('Por medir', 'gris'),
    ESTADO_MEDIDA: ('Medida y pesada', 'azul'),
    ESTADO_EN_REGISTRO: ('En prensa / registro', 'ambar'),
    ESTADO_TERMINADA: ('Rota', 'verde'),
    ESTADO_DEVUELTA: ('Devuelta', 'rojo'),
}

CAMPOS_MEDIDA = ('masa_g', 'd1', 'd2', 'l1', 'l2', 'l3')


def fecha_prevista(muestra):
    """RN-12: moldeo + edad; si no, la fecha programada de la recepción; si no, None."""
    if muestra.fecha_fabricacion and muestra.edad_ensayo_dias is not None:
        return muestra.fecha_fabricacion + timedelta(days=muestra.edad_ensayo_dias)
    return muestra.recepcion.fecha_ensayo_programado


def leer_fecha(texto, defecto):
    try:
        return date.fromisoformat((texto or '').strip())
    except ValueError:
        return defecto


def _estado(ensayo):
    if ensayo is None:
        return ESTADO_POR_MEDIR
    if ensayo.terminado:
        return ESTADO_TERMINADA
    if ensayo.observacion_revision:
        return ESTADO_DEVUELTA
    if ensayo.carga_kn is not None or ensayo.fotos_contadas:
        return ESTADO_EN_REGISTRO
    if all(getattr(ensayo, c) is not None for c in CAMPOS_MEDIDA):
        return ESTADO_MEDIDA
    return ESTADO_POR_MEDIR


def _ensayo(detalle):
    try:
        return detalle.resultado
    except ResultadoEnsayo.DoesNotExist:
        return None


def _candidatas(user, fecha):
    """Líneas visibles para el usuario que pueden caer en el programa de `fecha`.

    Las pendientes (sin resultado cerrado) y las terminadas ese mismo día. El
    técnico solo ve lo suyo, igual que en «Resultados».
    """
    qs = DetalleSolicitudEnsayo.objects.all()
    if not ve_todos_los_ensayos(user):
        qs = qs.filter(tecnico_asignado__user=user)
    cerrado = Q(resultado__estado__in=ResultadoEnsayo.ESTADOS_CERRADOS)
    qs = qs.filter(~cerrado | Q(cerrado, resultado__fecha_ensayo=fecha))
    return (
        qs.select_related(
            'muestra__recepcion', 'solicitud__cotizacion__cliente', 'resultado',
            'tecnico_asignado', 'servicio_cotizado__servicio',
        )
        .annotate(n_fotos=Count('resultado__fotos'))
        .order_by('muestra__codigo_laboratorio', 'pk')
    )


def lineas_del_dia(user, fecha, hoy):
    """Las probetas de compresión del programa de `fecha`.

    Devuelve (del_dia, atrasadas, sin_fecha): listas de líneas con `prevista`,
    `ensayo`, `estado`, `estado_texto`, `estado_color` y `atrasada` anotados.
    Las atrasadas solo se buscan para el programa de hoy (RN-13).
    """
    del_dia, atrasadas, sin_fecha = [], [], []
    for d in _candidatas(user, fecha):
        e = _ensayo(d)
        plantilla = e.plantilla if e else ResultadoEnsayo.plantilla_para(d)
        if plantilla != ResultadoEnsayo.PLANTILLA_COMPRESION:
            continue
        d.ensayo = e
        if e is not None:
            e.fotos_contadas = d.n_fotos
        d.prevista = fecha_prevista(d.muestra)
        d.estado = _estado(e)
        d.estado_texto, d.estado_color = ESTADOS[d.estado]
        d.atrasada = False
        terminada = d.estado == ESTADO_TERMINADA
        if terminada:
            if e.fecha_ensayo == fecha:
                del_dia.append(d)
        elif d.prevista == fecha:
            del_dia.append(d)
        elif d.prevista is None:
            sin_fecha.append(d)
        elif fecha == hoy and d.prevista < fecha:
            d.atrasada = True
            atrasadas.append(d)
    return del_dia, atrasadas, sin_fecha


def agrupar_por_cliente(lineas, ve_nombre):
    """Una «solicitud del día» por cliente (REQ-LIMS-63), en orden de llegada del código.

    El técnico nunca ve el nombre del cliente: se muestra su código confidencial.
    """
    grupos = OrderedDict()
    for d in lineas:
        cliente = d.solicitud.cotizacion.cliente
        g = grupos.get(cliente.pk)
        if g is None:
            g = grupos[cliente.pk] = {
                'cliente_id': cliente.pk,
                'nombre': cliente.razon_social if ve_nombre else (cliente.codigo_confidencial or f'Cliente {cliente.pk}'),
                'lineas': [],
                'solicitudes': OrderedDict(),
            }
        g['lineas'].append(d)
        g['solicitudes'][d.solicitud_id] = d.solicitud
    for g in grupos.values():
        lineas_g = g['lineas']
        g['total'] = len(lineas_g)
        g['rotas'] = sum(1 for d in lineas_g if d.estado == ESTADO_TERMINADA)
        g['medidas'] = sum(1 for d in lineas_g if d.estado != ESTADO_POR_MEDIR)
        g['atrasadas'] = sum(1 for d in lineas_g if d.atrasada)
        g['edades'] = sorted({d.muestra.edad_ensayo_dias for d in lineas_g if d.muestra.edad_ensayo_dias is not None})
        g['porcentaje'] = round(g['rotas'] * 100 / g['total']) if g['total'] else 0
        g['solicitudes'] = list(g['solicitudes'].values())
    return list(grupos.values())
