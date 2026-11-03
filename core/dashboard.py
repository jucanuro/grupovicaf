"""Cálculos del dashboard del LIMS (VCF-LIMS, specs/VCF-LIMS/requirements.md).

Funciones puras: reciben el periodo, el usuario y la fecha de hoy y devuelven
diccionarios listos para la plantilla. Todo se resuelve con agregaciones en la
BD, con un número fijo de consultas que no crece con los datos (REQ-LIMS-21).

Reglas de cálculo (RN-01 a RN-08) documentadas en la spec.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, Min, Q
from django.db.models.functions import TruncMonth, TruncWeek

from clientes.models import Cliente
from proyectos.models import DetalleSolicitudEnsayo, InformeFinal, Proyecto, SolicitudEnsayo
from servicios.models import Cotizacion
from trabajadores.permissions import ve_todos_los_ensayos

MESES_CORTOS = ('Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Dic')

PERIODOS = (
    ('mes', 'Este mes'),
    ('6m', 'Últimos 6 meses'),
    ('12m', '12 meses'),
    ('rango', 'Rango'),
)
PERIODO_POR_DEFECTO = '6m'
_MESES_POR_PERIODO = {'mes': 1, '6m': 6, '12m': 12}

ESTADOS_SOLICITUD_ABIERTOS = ('pendiente', 'proceso')
MAX_VENCIDAS_LISTADAS = 5
SEMANAS_ENSAYOS = 12
MESES_SPARKLINE = 12


# ---------------------------------------------------------------------------
# Periodo (RN-06)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Periodo:
    clave: str
    desde: date
    hasta: date
    meses: int | None = None  # None en un rango libre

    @property
    def dias(self):
        return (self.hasta - self.desde).days + 1


def _primer_dia_mes(d):
    return d.replace(day=1)


def _sumar_meses(d, n):
    """Corre una fecha n meses (n puede ser negativo) ajustando el día al fin de mes."""
    total = d.year * 12 + (d.month - 1) + n
    anio, mes = divmod(total, 12)
    mes += 1
    siguiente = date(anio + (mes // 12), mes % 12 + 1, 1)
    ultimo_dia = (siguiente - timedelta(days=1)).day
    return date(anio, mes, min(d.day, ultimo_dia))


def _parsear_fecha(valor):
    try:
        return date.fromisoformat((valor or '').strip())
    except ValueError:
        return None


def resolver_periodo(params, hoy):
    """Lee `periodo`, `desde` y `hasta` del GET. Un valor inválido cae al periodo por defecto."""
    clave = params.get('periodo') or PERIODO_POR_DEFECTO
    if clave == 'rango':
        desde = _parsear_fecha(params.get('desde'))
        hasta = _parsear_fecha(params.get('hasta'))
        if desde and hasta:
            if desde > hasta:
                desde, hasta = hasta, desde
            return Periodo('rango', desde, hasta)
        clave = PERIODO_POR_DEFECTO
    meses = _MESES_POR_PERIODO.get(clave)
    if meses is None:
        clave, meses = PERIODO_POR_DEFECTO, _MESES_POR_PERIODO[PERIODO_POR_DEFECTO]
    desde = _sumar_meses(_primer_dia_mes(hoy), -(meses - 1))
    return Periodo(clave, desde, hoy, meses)


def periodo_anterior(periodo):
    """El mismo tramo corrido N meses atrás, o los mismos días justo antes en un rango."""
    if periodo.meses:
        return Periodo(
            periodo.clave,
            _sumar_meses(periodo.desde, -periodo.meses),
            _sumar_meses(periodo.hasta, -periodo.meses),
            periodo.meses,
        )
    hasta = periodo.desde - timedelta(days=1)
    return Periodo(periodo.clave, hasta - timedelta(days=periodo.dias - 1), hasta)


def _meses_entre(desde, hasta):
    mes = _primer_dia_mes(desde)
    fin = _primer_dia_mes(hasta)
    meses = []
    while mes <= fin:
        meses.append(mes)
        mes = _sumar_meses(mes, 1)
    return meses


def _etiqueta_mes(mes, con_anio):
    nombre = MESES_CORTOS[mes.month - 1]
    return f'{nombre} {mes.year % 100:02d}' if con_anio else nombre


def _como_fecha(valor):
    """TruncMonth/TruncWeek devuelven date o datetime según el motor."""
    return valor.date() if hasattr(valor, 'date') and callable(valor.date) else valor


def _porcentaje(parte, total):
    return round(parte * 100 / total) if total else None


def _ancho(parte, maximo):
    """Ancho proporcional (0-100) para barras HTML; 0 no dibuja nada."""
    return round(parte * 100 / maximo, 1) if maximo else 0


# ---------------------------------------------------------------------------
# Bloques
# ---------------------------------------------------------------------------

def _cotizaciones_reales():
    # REQ-LIMS-25: las plantillas no son cotizaciones emitidas.
    return Cotizacion.objects.filter(es_plantilla=False)


def _bloque_comercial(periodo):
    cotizaciones = _cotizaciones_reales().filter(fecha_generacion__range=(periodo.desde, periodo.hasta))
    por_estado = {
        fila['estado']: fila['n']
        for fila in cotizaciones.values('estado').annotate(n=Count('id'))
    }
    pendientes = por_estado.get('Pendiente', 0)
    enviadas_estado = por_estado.get('Enviada', 0)
    aceptadas = por_estado.get('Aceptada', 0)
    rechazadas = por_estado.get('Rechazada', 0)
    anuladas = por_estado.get('Anulada', 0)
    emitidas = sum(por_estado.values())
    enviadas = enviadas_estado + aceptadas + rechazadas  # RN-02
    decididas = aceptadas + rechazadas

    anterior = periodo_anterior(periodo)
    emitidas_anterior = _cotizaciones_reales().filter(
        fecha_generacion__range=(anterior.desde, anterior.hasta),
    ).count()
    diferencia = emitidas - emitidas_anterior

    # Barras apiladas por mes (REQ-LIMS-06).
    meses = _meses_entre(periodo.desde, periodo.hasta)
    con_anio = meses[0].year != meses[-1].year
    serie = {mes: {'aceptadas': 0, 'en_gestion': 0, 'perdidas': 0} for mes in meses}
    filas = (
        cotizaciones.annotate(mes=TruncMonth('fecha_generacion'))
        .values('mes', 'estado').annotate(n=Count('id'))
    )
    for fila in filas:
        mes = _como_fecha(fila['mes'])
        if mes not in serie:
            continue
        if fila['estado'] == 'Aceptada':
            serie[mes]['aceptadas'] += fila['n']
        elif fila['estado'] in ('Rechazada', 'Anulada'):
            serie[mes]['perdidas'] += fila['n']
        else:
            serie[mes]['en_gestion'] += fila['n']
    por_mes = [
        {
            'etiqueta': _etiqueta_mes(mes, con_anio),
            'etiqueta_larga': f'{MESES_CORTOS[mes.month - 1]} {mes.year}',
            **valores,
            'total': sum(valores.values()),
        }
        for mes, valores in serie.items()
    ]

    embudo = [
        {'etiqueta': 'Emitidas', 'cantidad': emitidas, 'ancho': _ancho(emitidas, emitidas)},
        {'etiqueta': 'Enviadas al cliente', 'cantidad': enviadas, 'ancho': _ancho(enviadas, emitidas)},
        {'etiqueta': 'Aceptadas', 'cantidad': aceptadas, 'ancho': _ancho(aceptadas, emitidas)},
    ]

    return {
        'emitidas': emitidas,
        'emitidas_anterior': emitidas_anterior,
        'diferencia': abs(diferencia),
        'tendencia': 'sube' if diferencia > 0 else 'baja' if diferencia < 0 else 'igual',
        'pendientes': pendientes,
        'enviadas': enviadas,
        'en_gestion': pendientes + enviadas_estado,
        'aceptadas': aceptadas,
        'rechazadas': rechazadas,
        'anuladas': anuladas,
        'decididas': decididas,
        'tasa_aceptacion': _porcentaje(aceptadas, decididas),  # RN-03
        'conversion_global': _porcentaje(aceptadas, emitidas),  # RN-03
        'pct_enviadas': _porcentaje(enviadas, emitidas),
        'pct_aceptadas_de_enviadas': _porcentaje(aceptadas, enviadas),
        'embudo': embudo,
        'por_mes': por_mes,
        'tiene_datos': emitidas > 0,
    }


def _bloque_clientes(hoy, periodo):
    total = Cliente.objects.count()
    inicio_sparkline = _sumar_meses(_primer_dia_mes(hoy), -(MESES_SPARKLINE - 1))
    desde_consulta = min(inicio_sparkline, periodo.desde)
    # RN-05: un cliente es nuevo en el mes de su primera cotización real.
    primeras = (
        Cliente.objects
        .annotate(primera=Min('cotizaciones__fecha_generacion', filter=Q(cotizaciones__es_plantilla=False)))
        .filter(primera__gte=desde_consulta, primera__lte=hoy)
        .values_list('primera', flat=True)
    )
    nuevos_periodo = 0
    por_mes = {mes: 0 for mes in _meses_entre(inicio_sparkline, hoy)}
    for primera in primeras:
        if periodo.desde <= primera <= periodo.hasta:
            nuevos_periodo += 1
        mes = _primer_dia_mes(primera)
        if mes in por_mes:
            por_mes[mes] += 1

    valores = list(por_mes.values())
    return {
        'total': total,
        'nuevos_periodo': nuevos_periodo,
        'sparkline': _sparkline(valores),
        'sparkline_valores': [
            {'etiqueta': f'{MESES_CORTOS[mes.month - 1]} {mes.year}', 'cantidad': n}
            for mes, n in por_mes.items()
        ],
    }


def _sparkline(valores, ancho=120, alto=36, margen=4):
    """Puntos de un <polyline> SVG; el último punto se marca aparte."""
    if not valores:
        return {'puntos': '', 'x': 0, 'y': 0}
    maximo = max(valores) or 1
    paso = (ancho - margen * 2) / max(len(valores) - 1, 1)
    puntos = [
        (round(margen + i * paso, 1), round(alto - margen - v * (alto - margen * 2) / maximo, 1))
        for i, v in enumerate(valores)
    ]
    x, y = puntos[-1]
    return {'puntos': ' '.join(f'{px},{py}' for px, py in puntos), 'x': x, 'y': y}


def _bloque_laboratorio(periodo, user, hoy):
    solicitudes = SolicitudEnsayo.objects.filter(fecha_solicitud__range=(periodo.desde, periodo.hasta))
    por_estado = {
        fila['estado']: fila['n']
        for fila in solicitudes.values('estado').annotate(n=Count('id'))
    }
    total = sum(por_estado.values())
    segmentos = [
        {'clave': 'pendiente', 'etiqueta': 'Pendientes', 'cantidad': por_estado.get('pendiente', 0),
         'color': '#86b6ef', 'texto': '#0b0b0b'},
        {'clave': 'proceso', 'etiqueta': 'En proceso', 'cantidad': por_estado.get('proceso', 0),
         'color': '#2a78d6', 'texto': '#ffffff'},
        {'clave': 'finalizado', 'etiqueta': 'Finalizadas', 'cantidad': por_estado.get('finalizado', 0),
         'color': '#104281', 'texto': '#ffffff'},
    ]
    for segmento in segmentos:
        segmento['porcentaje'] = _porcentaje(segmento['cantidad'], total) or 0

    # RN-04: foto de hoy, sin periodo. REQ-LIMS-15: el técnico solo ve lo suyo.
    vencidas_qs = SolicitudEnsayo.objects.filter(
        estado__in=ESTADOS_SOLICITUD_ABIERTOS,
        fecha_entrega_programada__lt=hoy,
    )
    if not ve_todos_los_ensayos(user):
        ids = DetalleSolicitudEnsayo.objects.filter(tecnico_asignado__user=user).values('solicitud_id')
        vencidas_qs = vencidas_qs.filter(id__in=ids)
    vencidas_total = vencidas_qs.count()
    vencidas = [
        {
            'codigo': fila['codigo_solicitud'],
            'dias_atraso': (hoy - fila['fecha_entrega_programada']).days,
        }
        for fila in vencidas_qs.order_by('fecha_entrega_programada', 'id')
        .values('codigo_solicitud', 'fecha_entrega_programada')[:MAX_VENCIDAS_LISTADAS]
    ]

    # REQ-LIMS-14: ensayos finalizados por semana (lunes a domingo).
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    semanas = [lunes_actual - timedelta(weeks=n) for n in range(SEMANAS_ENSAYOS - 1, -1, -1)]
    por_semana = {semana: 0 for semana in semanas}
    filas = (
        DetalleSolicitudEnsayo.objects
        .filter(fecha_entrega_real__gte=semanas[0], fecha_entrega_real__lte=hoy)
        .annotate(semana=TruncWeek('fecha_entrega_real'))
        .values('semana').annotate(n=Count('id'))
    )
    for fila in filas:
        semana = _como_fecha(fila['semana'])
        if semana in por_semana:
            por_semana[semana] += fila['n']
    ensayos_semana = [
        {
            'etiqueta': f'Sem. {semana.isocalendar()[1]}',
            'etiqueta_larga': f'Semana {semana.isocalendar()[1]} (desde el {semana.day:02d}/{semana.month:02d})',
            'cantidad': n,
        }
        for semana, n in por_semana.items()
    ]

    return {
        'solicitudes_total': total,
        'segmentos': segmentos,
        'tiene_datos': total > 0,
        'vencidas_total': vencidas_total,
        'vencidas': vencidas,
        'ensayos_semana': ensayos_semana,
        'ensayos_semana_total': sum(por_semana.values()),
    }


def _bloque_proyectos(periodo):
    filas = (
        Proyecto.objects.filter(fecha_inicio__range=(periodo.desde, periodo.hasta))
        .values('estado').annotate(n=Count('id'))
    )
    por_estado = {fila['estado']: fila['n'] for fila in filas}
    total = sum(por_estado.values())
    maximo = max(por_estado.values(), default=0)
    etapas = [
        {
            'clave': clave,
            'etiqueta': etiqueta,
            'cantidad': por_estado.get(clave, 0),
            'ancho': _ancho(por_estado.get(clave, 0), maximo),
            'color': '#a9a8a1' if clave == 'CANCELADO' else '#2a78d6',
        }
        for clave, etiqueta in Proyecto.ESTADOS_PROYECTO
    ]
    return {'total': total, 'etapas': etapas, 'tiene_datos': total > 0}


def _bloque_informes(periodo):
    return {
        'por_enviar': InformeFinal.objects.filter(estado_envio='pendiente').count(),
        'emitidos_periodo': InformeFinal.objects.filter(
            fecha_emision__date__range=(periodo.desde, periodo.hasta),
        ).count(),
    }


def construir_dashboard(periodo, user, hoy):
    comercial = _bloque_comercial(periodo)
    laboratorio = _bloque_laboratorio(periodo, user, hoy)
    return {
        'periodo': periodo,
        'periodos': PERIODOS,
        'clientes': _bloque_clientes(hoy, periodo),
        'comercial': comercial,
        'laboratorio': laboratorio,
        'proyectos': _bloque_proyectos(periodo),
        'informes': _bloque_informes(periodo),
        # Solo lo que dibuja Chart.js; viaja con json_script.
        'graficos': {
            'cotizaciones_mes': {
                'etiquetas': [m['etiqueta'] for m in comercial['por_mes']],
                'titulos': [m['etiqueta_larga'] for m in comercial['por_mes']],
                'aceptadas': [m['aceptadas'] for m in comercial['por_mes']],
                'en_gestion': [m['en_gestion'] for m in comercial['por_mes']],
                'perdidas': [m['perdidas'] for m in comercial['por_mes']],
            },
            'ensayos_semana': {
                'etiquetas': [s['etiqueta'] for s in laboratorio['ensayos_semana']],
                'titulos': [s['etiqueta_larga'] for s in laboratorio['ensayos_semana']],
                'valores': [s['cantidad'] for s in laboratorio['ensayos_semana']],
            },
        },
    }
