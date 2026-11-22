"""Avisos de la campana del LIMS (cabecera, `templates/cabecera_base.html`).

No hay una tabla de notificaciones: cada aviso es un conteo en vivo de lo que
el usuario tiene pendiente según sus permisos (lo mismo que vería entrando a
cada lista). Así no hay nada que marcar como leído y el aviso desaparece solo
cuando la tarea se hace. La campana los pide a `/notificaciones/` al cargar la
página (sin frenar el render) y muestra el punto rojo solo si hay alguno.
"""
from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from trabajadores.permissions import trabajador_tiene_permiso, ve_todos_los_ensayos


def _aviso(clave, cantidad, titulo, detalle, url, icono, tono):
    return {
        'clave': clave,
        'cantidad': cantidad,
        'titulo': titulo,
        'detalle': detalle,
        'url': url,
        'icono': icono,
        'tono': tono,
    }


def _cotizaciones_pendientes(user):
    from servicios.models import Cotizacion

    n = Cotizacion.objects.filter(estado='Pendiente', es_plantilla=False).count()
    if not n:
        return None
    return _aviso(
        'cotizaciones_pendientes', n,
        'Cotizaciones pendientes de revisión',
        'Revisa y envía al cliente.',
        reverse('servicios:lista_cotizaciones') + '?estado=Pendiente',
        'file-signature', 'emerald',
    )


def _solicitudes_web(user):
    from web_contacto.models import SolicitudCotizacionWeb

    n = SolicitudCotizacionWeb.objects.filter(cotizacion__isnull=True).count()
    if not n:
        return None
    return _aviso(
        'solicitudes_web', n,
        'Solicitudes de cotización desde la web',
        'Pedidos del formulario público sin atender.',
        reverse('servicios:lista_solicitudes_web'),
        'globe', 'sky',
    )


def _proyectos_vencidos(user):
    from proyectos.models import Proyecto

    n = Proyecto.objects.filter(
        fecha_entrega_estimada__lt=timezone.localdate(),
    ).exclude(estado__in=['FINALIZADO', 'CANCELADO']).count()
    if not n:
        return None
    return _aviso(
        'proyectos_vencidos', n,
        'Proyectos con entrega vencida',
        'Pasó su fecha de entrega estimada.',
        reverse('proyectos:lista_proyectos_pendientes'),
        'alarm-clock', 'rose',
    )


def _ensayos_por_registrar(user):
    from proyectos.models import DetalleSolicitudEnsayo, ResultadoEnsayo

    qs = DetalleSolicitudEnsayo.objects.exclude(
        resultado__estado__in=ResultadoEnsayo.ESTADOS_CERRADOS,
    )
    if not ve_todos_los_ensayos(user):
        qs = qs.filter(tecnico_asignado__user=user)
    n = qs.count()
    if not n:
        return None
    return _aviso(
        'ensayos_por_registrar', n,
        'Ensayos por registrar',
        'Líneas de ensayo sin resultado terminado.',
        reverse('proyectos:mis_ensayos_compresion'),
        'flask-conical', 'orange',
    )


def _resultados_por_revisar(user):
    from proyectos.models import ResultadoEnsayo

    n = ResultadoEnsayo.objects.filter(estado=ResultadoEnsayo.ESTADO_TERMINADO) \
        .values('detalle__solicitud').distinct().count()
    if not n:
        return None
    return _aviso(
        'resultados_por_revisar', n,
        'Solicitudes con resultados por revisar',
        'Resultados terminados esperando aprobación.',
        reverse('proyectos:revision_compresion_lista'),
        'clipboard-check', 'violet',
    )


def _actividades_hoy(user):
    from actividades.models import CalendarioActividad

    inicio = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    fin = inicio + timedelta(days=1)
    n = CalendarioActividad.objects.filter(
        Q(creado_por=user) | Q(participantes__trabajador__user=user),
        fecha_inicio__lt=fin,
        fecha_fin__gte=inicio,
    ).exclude(estado__in=['COMPLETADA', 'CANCELADA']).distinct().count()
    if not n:
        return None
    return _aviso(
        'actividades_hoy', n,
        'Actividades para hoy',
        'Tus actividades del calendario de hoy.',
        reverse('actividades:calendario_dashboard'),
        'calendar-days', 'amber',
    )


# (permiso que hace falta, función que arma el aviso)
_FUENTES = (
    ('cotizaciones.ver', _cotizaciones_pendientes),
    ('cotizaciones.ver', _solicitudes_web),
    ('proyectos.ver', _proyectos_vencidos),
    ('ensayos.registrar', _ensayos_por_registrar),
    ('informes.aprobar', _resultados_por_revisar),
    ('calendario.ver', _actividades_hoy),
)


def avisos_de(user):
    """Lista de avisos con cantidad > 0 que el usuario puede ver."""
    avisos = []
    for permiso, fuente in _FUENTES:
        if not trabajador_tiene_permiso(user, permiso):
            continue
        aviso = fuente(user)
        if aviso:
            avisos.append(aviso)
    return avisos
