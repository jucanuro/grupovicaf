"""Avance por muestra de cada proyecto (HU-LIMS-19, REQ-LIMS-44 a 52).

El panel de proyectos ya no muestra una sola «etapa» del proyecto: cuenta en
qué punto del flujo está cada muestra y elige la acción más urgente.

Etapas de una muestra (RN-09), en el orden del flujo:

    por_ingresar → recibida → en_ensayo → informe

- **Por ingresar**: previstas en la cotización (`Proyecto.numero_muestras`)
  que todavía no tienen fila en `MuestraDetalle`.
- **Recibida**: registrada en una recepción, sin ensayo asignado.
- **En ensayo**: tiene al menos una línea `DetalleSolicitudEnsayo` y su
  solicitud todavía no tiene `InformeFinal`.
- **Informe**: la solicitud de su recepción ya tiene `InformeFinal`.

Todo se calcula con un número fijo de consultas por página, sin importar
cuántos proyectos o muestras haya.
"""
from django.db.models import Count, Exists, OuterRef
from django.urls import reverse

from trabajadores.permissions import trabajador_tiene_permiso

from .models import DetalleSolicitudEnsayo, InformeFinal, MuestraDetalle, Proyecto, SolicitudEnsayo

# RN-10: peso de cada etapa en el % de avance (0 = nada hecho, 3 = informe).
PESO_ETAPA = {'por_ingresar': 0, 'recibida': 1, 'en_ensayo': 2, 'informe': 3}
PESO_MAXIMO = 3

ETAPAS = (
    # clave, etiqueta, permiso para abrir su pantalla
    ('por_ingresar', 'Por ingresar', 'muestras.crear'),
    ('recibida', 'Recibidas', 'muestras.ver'),
    ('en_ensayo', 'En ensayo', 'ensayos.ver'),
    ('informe', 'Con informe', 'informes.ver'),
)


def proyecto_de_filtro(request):
    """El proyecto de `?proyecto=<id>` (los botones del panel lo envían) o None."""
    valor = (request.GET.get('proyecto') or '').strip()
    if not valor.isdigit():
        return None
    return (
        Proyecto.objects.filter(pk=int(valor))
        .only('id', 'nombre_proyecto', 'codigo_proyecto', 'cotizacion_id')
        .first()
    )


def _url_etapa(clave, proyecto_id):
    if clave == 'por_ingresar':
        return reverse('proyectos:crear_recepcion_desde_proyecto', args=[proyecto_id])
    nombre = {
        'recibida': 'proyectos:lista_recepciones',
        'en_ensayo': 'proyectos:lista_solicitudes',
        'informe': 'proyectos:lista_informes',
    }[clave]
    return f'{reverse(nombre)}?proyecto={proyecto_id}'


def _plural(n, singular, plural):
    return f'{n} {singular if n == 1 else plural}'


def _accion_urgente(proyecto_id, conteo, informes_pendientes, total, permisos):
    """RN-11: la acción más urgente, en este orden de prioridad."""
    if total == 0:
        return {
            'tipo': 'registrar', 'texto': 'Registrar muestras', 'permiso': permisos['muestras.crear'],
            'url': _url_etapa('por_ingresar', proyecto_id),
        }
    if conteo['por_ingresar']:
        return {
            'tipo': 'registrar',
            'texto': f"Registrar {_plural(conteo['por_ingresar'], 'muestra', 'muestras')}",
            'permiso': permisos['muestras.crear'],
            'url': _url_etapa('por_ingresar', proyecto_id),
        }
    if informes_pendientes:
        # Se abre la revisión de la solicitud más antigua: desde ahí se
        # aprueba y se pasa al editor del informe (CLAUDE.md, fase 2).
        cantidad, solicitud_id = informes_pendientes
        return {
            'tipo': 'informe',
            'texto': 'Revisar y emitir informe' if cantidad == 1 else f'Revisar y emitir informes (1 de {cantidad})',
            'permiso': permisos['informes.aprobar'],
            'url': reverse('proyectos:revision_compresion', args=[solicitud_id]),
        }
    if conteo['recibida']:
        return {
            'tipo': 'solicitud',
            'texto': f"Asignar ensayos a {_plural(conteo['recibida'], 'muestra', 'muestras')}",
            'permiso': permisos['ensayos.crear'],
            'url': f"{reverse('proyectos:crear_solicitud')}?proyecto={proyecto_id}",
        }
    if conteo['en_ensayo']:
        return {
            'tipo': 'ensayo',
            'texto': f"Seguir {_plural(conteo['en_ensayo'], 'muestra', 'muestras')} en ensayo",
            'permiso': permisos['ensayos.ver'],
            'url': _url_etapa('en_ensayo', proyecto_id),
        }
    return {
        'tipo': 'completo', 'texto': 'Ver informes', 'permiso': permisos['informes.ver'],
        'url': _url_etapa('informe', proyecto_id),
    }


def calcular_avance(proyectos, user):
    """Añade `proyecto.avance` a cada proyecto de la lista (una página del panel)."""
    proyectos = list(proyectos)
    codigos = {'muestras.crear', 'muestras.ver', 'ensayos.ver', 'ensayos.crear', 'informes.ver', 'informes.aprobar'}
    permisos = {codigo: trabajador_tiene_permiso(user, codigo) for codigo in codigos}

    cotizaciones = {p.cotizacion_id for p in proyectos if p.cotizacion_id}
    por_cotizacion = {c: {clave: 0 for clave, _, _ in ETAPAS} for c in cotizaciones}

    muestras = (
        MuestraDetalle.objects.filter(recepcion__cotizacion_id__in=cotizaciones)
        .annotate(
            con_ensayo=Exists(DetalleSolicitudEnsayo.objects.filter(muestra=OuterRef('pk'))),
            con_informe=Exists(InformeFinal.objects.filter(solicitud__recepcion=OuterRef('recepcion'))),
        )
        .values('recepcion__cotizacion_id', 'con_ensayo', 'con_informe')
        .annotate(n=Count('id'))
    )
    for fila in muestras:
        if fila['con_informe']:
            clave = 'informe'
        elif fila['con_ensayo']:
            clave = 'en_ensayo'
        else:
            clave = 'recibida'
        por_cotizacion[fila['recepcion__cotizacion_id']][clave] += fila['n']

    # Solicitudes con todos los ensayos terminados que aún esperan su informe.
    informes_pendientes = {}
    for cotizacion_id, solicitud_id in (
        SolicitudEnsayo.objects.filter(
            cotizacion_id__in=cotizaciones, estado='finalizado', informe_final__isnull=True,
        ).order_by('fecha_solicitud', 'id').values_list('cotizacion_id', 'id')
    ):
        cantidad, primera = informes_pendientes.get(cotizacion_id, (0, solicitud_id))
        informes_pendientes[cotizacion_id] = (cantidad + 1, primera)

    for proyecto in proyectos:
        if not proyecto.cotizacion_id:
            proyecto.avance = {'sin_cotizacion': True, 'porcentaje': 0, 'etapas': [], 'accion': None}
            continue
        conteo = dict(por_cotizacion[proyecto.cotizacion_id])
        registradas = conteo['recibida'] + conteo['en_ensayo'] + conteo['informe']
        conteo['por_ingresar'] = max((proyecto.numero_muestras or 0) - registradas, 0)
        total = registradas + conteo['por_ingresar']
        puntos = sum(PESO_ETAPA[clave] * n for clave, n in conteo.items())
        porcentaje = round(puntos * 100 / (total * PESO_MAXIMO)) if total else 0

        etapas = [
            {
                'clave': clave,
                'etiqueta': etiqueta,
                'cantidad': conteo[clave],
                'url': _url_etapa(clave, proyecto.id) if permisos[permiso] else None,
            }
            for clave, etiqueta, permiso in ETAPAS
        ]
        accion = _accion_urgente(proyecto.id, conteo, informes_pendientes.get(proyecto.cotizacion_id),
                                 total, permisos)
        proyecto.avance = {
            'sin_cotizacion': False,
            'porcentaje': porcentaje,
            'completo': total > 0 and conteo['informe'] == total,
            'total': total,
            'registradas': registradas,
            'etapas': etapas,
            'accion': accion,
        }
    return proyectos


def filtrar_por_proyecto(queryset, proyecto, campo_cotizacion='cotizacion_id'):
    """Acota una lista al proyecto del filtro; sin cotización no hay nada que mostrar."""
    if proyecto is None:
        return queryset
    if not proyecto.cotizacion_id:
        return queryset.none()
    return queryset.filter(**{campo_cotizacion: proyecto.cotizacion_id})


# ---------------------------------------------------------------------------
# Pestañas y filtro por fecha del panel (HU-LIMS-25, REQ-LIMS-97 a 102).
# ---------------------------------------------------------------------------

# RN-14: cada proyecto cae en UNA pestaña según su acción más urgente (RN-11),
# en el orden del flujo. Así ninguna pestaña repite proyectos.
PESTANAS = (
    ('todos', 'Todos', 'layout-grid'),
    ('muestras', 'Muestras', 'flask-conical'),
    ('ensayo', 'En ensayo', 'hammer'),
    ('informes', 'Por emitir informe', 'file-pen-line'),
    ('completos', 'Con informe', 'file-check-2'),
)
_PESTANA_POR_ACCION = {
    'registrar': 'muestras',
    'solicitud': 'muestras',
    'ensayo': 'ensayo',
    'informe': 'informes',
    'completo': 'completos',
}

PERIODOS = (
    ('', 'Todas las fechas'),
    ('7', 'Últimos 7 días'),
    ('30', 'Últimos 30 días'),
    ('90', 'Últimos 3 meses'),
    ('mes', 'Este mes'),
    ('anio', 'Este año'),
    ('rango', 'Elegir fechas…'),
)


def pestana_de(valor):
    claves = {clave for clave, _, _ in PESTANAS}
    return valor if valor in claves else 'todos'


def pestana_del_proyecto(proyecto):
    """RN-14. Sin cotización cuenta como «Muestras»: lo primero es vincularla."""
    av = proyecto.avance
    if av['sin_cotizacion'] or not av['accion']:
        return 'muestras'
    return _PESTANA_POR_ACCION.get(av['accion']['tipo'], 'muestras')


def contar_pestanas(proyectos, activa):
    conteo = {clave: 0 for clave, _, _ in PESTANAS}
    for p in proyectos:
        conteo[pestana_del_proyecto(p)] += 1
    conteo['todos'] = len(proyectos)
    return [
        {'clave': clave, 'etiqueta': etiqueta, 'icono': icono, 'cantidad': conteo[clave], 'activa': clave == activa}
        for clave, etiqueta, icono in PESTANAS
    ]


def _fecha(texto):
    from datetime import date
    try:
        return date.fromisoformat((texto or '').strip())
    except ValueError:
        return None


def filtro_fechas_panel(params, hoy=None):
    """RN-15: periodo rápido o rango propio sobre la fecha de inicio del proyecto."""
    from datetime import timedelta
    from django.utils import timezone

    hoy = hoy or timezone.localdate()
    periodo = params.get('periodo', '')
    if periodo not in {clave for clave, _ in PERIODOS}:
        periodo = ''
    desde = hasta = None
    if periodo in ('7', '30', '90'):
        desde = hoy - timedelta(days=int(periodo) - 1)
    elif periodo == 'mes':
        desde = hoy.replace(day=1)
    elif periodo == 'anio':
        desde = hoy.replace(month=1, day=1)
    elif periodo == 'rango' or (not periodo and (params.get('desde') or params.get('hasta'))):
        periodo = 'rango'
        desde, hasta = _fecha(params.get('desde')), _fecha(params.get('hasta'))
        if desde and hasta and desde > hasta:
            desde, hasta = hasta, desde
    return {
        'periodo': periodo,
        'desde': desde,
        'hasta': hasta,
        'periodos': [{'clave': c, 'etiqueta': e, 'activo': c == periodo} for c, e in PERIODOS],
    }
