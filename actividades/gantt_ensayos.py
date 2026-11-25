"""Gantt de ensayos (HU-LIMS-22, REQ-LIMS-74 a 82).

Una fila por línea de solicitud (`DetalleSolicitudEnsayo`): el estado y el
avance salen de su `ResultadoEnsayo` (DP-01), no de los días transcurridos.
El atraso es la distancia entre la entrega programada y hoy mientras la línea
no esté terminada (REQ-LIMS-77). Todo lo visual vive en `static/js/gantt.js`.
"""
from datetime import timedelta

from django.db.models import Max
from django.urls import reverse

from proyectos.models import DetalleSolicitudEnsayo, FotoEnsayo, ResultadoEnsayo
from trabajadores.permissions import nombre_cliente_visible

# Estado de la línea → (texto, grupo de color). Grupos: pend, proc, ok.
ESTADOS = {
    'sin_empezar': ('Sin empezar', 'pend'),
    'registro': ('En registro', 'proc'),
    'devuelto': ('Devuelto', 'proc'),
    'terminado': ('Terminado', 'ok'),
    'aprobado': ('Aprobado', 'ok'),
}
AVANCE_MIN_REGISTRO = 5
AVANCE_MAX_REGISTRO = 95


def _resultado(detalle):
    try:
        return detalle.resultado
    except ResultadoEnsayo.DoesNotExist:
        return None


def _requisitos(resultado):
    """(hechos, total) de los datos y fotos que pide la plantilla para terminar.

    Es la misma lista que `ResultadoEnsayo.faltantes_para_terminar`, contada
    con las fotos ya precargadas para no hacer una consulta por línea.
    """
    tipos = [codigo for codigo, _ in FotoEnsayo.tipos_de(resultado.plantilla)]
    cargadas = {f.tipo for f in resultado.fotos.all()}
    fotos = [t in cargadas for t in tipos]
    if resultado.es_compresion:
        muestra = resultado.detalle.muestra
        datos = [
            bool(getattr(muestra, 'fecha_fabricacion', None) and getattr(muestra, 'fc_diseno', None)),
            bool(resultado.fecha_ensayo),
            *[getattr(resultado, c) not in (None, '') for c in ResultadoEnsayo.CAMPOS_MEDIDOS],
            bool(resultado.tipo_fractura),
            resultado.verif_perpendicularidad is not None,
            resultado.verif_planitud is not None,
        ]
    else:
        datos = [
            bool(resultado.fecha_ensayo),
            bool((resultado.resumen or '').strip()),
            bool(resultado.hoja_calculo),
        ]
    marcas = datos + fotos
    return sum(marcas), len(marcas)


def estado_y_avance(resultado):
    """(clave de estado, % de avance) de una línea según su resultado (REQ-LIMS-75)."""
    if resultado is None:
        return 'sin_empezar', 0
    if resultado.estado == ResultadoEnsayo.ESTADO_APROBADO:
        return 'aprobado', 100
    if resultado.estado == ResultadoEnsayo.ESTADO_TERMINADO:
        return 'terminado', 100
    hechos, total = _requisitos(resultado)
    avance = round(hechos * 100 / total) if total else AVANCE_MIN_REGISTRO
    avance = max(AVANCE_MIN_REGISTRO, min(AVANCE_MAX_REGISTRO, avance))
    clave = 'devuelto' if (resultado.observacion_revision or '').strip() else 'registro'
    return clave, avance


def _iniciales(nombre):
    partes = [p for p in (nombre or '').split() if p]
    if not partes:
        return '?'
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[1][0]).upper()


def lineas_de_ensayo(user, ve_todos, hoy, desde, hasta, cotizacion_id=None, responsable_id=None):
    """Lista de diccionarios para el JSON del Gantt, una por línea visible."""
    detalles = DetalleSolicitudEnsayo.objects.filter(
        solicitud__fecha_solicitud__gte=desde,
        solicitud__fecha_solicitud__lte=hasta,
    ).select_related(
        'solicitud',
        'solicitud__cotizacion__cliente',
        'muestra',
        'servicio_cotizado__servicio',
        'tecnico_asignado__user',
        'resultado',
    ).prefetch_related('resultado__fotos').order_by('solicitud__fecha_solicitud', 'solicitud_id', 'muestra__codigo_laboratorio', 'id')

    if cotizacion_id:
        detalles = detalles.filter(solicitud__cotizacion_id=cotizacion_id)
    if responsable_id:
        detalles = detalles.filter(tecnico_asignado_id=responsable_id)
    if not ve_todos:
        # REQ-LIMS-82: el técnico solo ve sus líneas.
        detalles = detalles.filter(tecnico_asignado__user=user)

    detalles = list(detalles)
    # REQ-LIMS-78 (DP-03): la entrega de la solicitud es la última fecha
    # programada de TODAS sus líneas, también las que este usuario no ve.
    entregas = dict(
        DetalleSolicitudEnsayo.objects
        .filter(solicitud_id__in={d.solicitud_id for d in detalles})
        .values('solicitud_id').annotate(fin=Max('fecha_entrega_programada'))
        .values_list('solicitud_id', 'fin')
    )

    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)
    datos = []
    for d in detalles:
        solicitud = d.solicitud
        resultado = _resultado(d)
        clave, avance = estado_y_avance(resultado)
        texto, grupo = ESTADOS[clave]
        cerrado = grupo == 'ok'

        inicio = solicitud.fecha_solicitud or hoy
        programada = d.fecha_entrega_programada or inicio
        # La barra nunca termina antes de empezar; el atraso se mide con la
        # fecha programada real (REQ-LIMS-77).
        fin = max(programada, inicio)
        atraso = (hoy - programada).days if (not cerrado and programada < hoy) else 0
        terminado_en = resultado.fecha_ensayo if (cerrado and resultado and resultado.fecha_ensayo) else None

        cliente = solicitud.cotizacion.cliente if solicitud.cotizacion_id else None
        # La descripción de la línea es lo que pidió el cliente; el servicio, el respaldo.
        ensayo = (d.descripcion_ensayo or '').strip()
        if not ensayo and d.servicio_cotizado_id and d.servicio_cotizado.servicio_id:
            ensayo = d.servicio_cotizado.servicio.nombre
        ensayo = ensayo or 'Ensayo'
        tecnico = d.tecnico_asignado
        tecnico_nombre = tecnico.nombre_completo if tecnico else 'Sin asignar'
        muestra = d.muestra.codigo_laboratorio if d.muestra_id else 'Sin muestra'
        entrega = entregas.get(solicitud.pk) or fin

        datos.append({
            'id': f'ensayo-detalle-{d.pk}',
            'db_id': d.pk,
            'tipo': 'ensayo',
            'start': inicio.isoformat(),
            'end': fin.isoformat(),
            'estado_linea': clave,
            'estado_texto': texto,
            'grupo': grupo,
            'avance': avance,
            'atraso_dias': atraso,
            'esta_vencido': atraso > 0,
            'entrega_semana': (not cerrado) and lunes <= programada <= domingo,
            'programada': programada.isoformat(),
            'terminado_mes': bool(terminado_en and terminado_en.year == hoy.year and terminado_en.month == hoy.month),
            'solicitud_id': solicitud.pk,
            'codigo_solicitud': solicitud.codigo_solicitud or f'SOL-{solicitud.pk}',
            'entrega_solicitud': entrega.isoformat(),
            'url_resultados': reverse('proyectos:resultados_solicitud', args=[solicitud.pk]),
            'cliente': nombre_cliente_visible(user, cliente, ve_todos) if cliente else '',
            'muestra': muestra,
            'servicio': ensayo,
            'norma': d.norma or '',
            'responsable': tecnico_nombre,
            'responsable_id': d.tecnico_asignado_id,
            'iniciales': _iniciales(tecnico_nombre) if tecnico else '—',
            # Campos de antes: los sigue leyendo quien consuma el JSON.
            'name': f'{muestra} · {ensayo}'[:140],
            'estado': (solicitud.estado or 'pendiente').upper(),
            'progress': avance,
            'clase': 'ENSAYO',
        })
    return datos
