import json
import logging
import re
from correo.permisos import puede_entrar_correo
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from clientes.models import Cliente
from proyectos.models import Proyecto, RecepcionMuestra, SolicitudEnsayo, InformeFinal, DetalleSolicitudEnsayo
from trabajadores.models import TrabajadorProfile
from trabajadores.permissions import (
    nombre_cliente_visible,
    permiso_requerido,
    trabajador_tiene_permiso,
    ve_todos_los_ensayos,
)

from .models import (
    CalendarioActividad,
    CalendarioCategoria,
    CalendarioMiembro,
    CalendarioParticipante,
    CalendarioRecordatorio,
)
from .gantt_ensayos import lineas_de_ensayo
from .tasks import enviar_aviso_cliente
from .visibilidad import actividades_visibles, calendarios_visibles, puede_crear_en

COLOR_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
CALENDARIO_ENSAYOS = 'ensayos'
COLOR_ENSAYOS = '#0891b2'
# Sin cliente, la actividad queda registrada como interna (pedido del Gerente).
ACTIVIDAD_INTERNA = 'Actividad interna'


def _cliente_visible(user, actividad, ve_todos):
    """Nombre del cliente que puede ver este usuario; sin cliente, «Actividad interna»."""
    if actividad.cliente:
        return nombre_cliente_visible(user, actividad.cliente, ve_todos)
    manual = (actividad.cliente_nombre_manual or '').strip()
    if not manual or manual == ACTIVIDAD_INTERNA:
        return ACTIVIDAD_INTERNA
    return manual if ve_todos else ''

logger = logging.getLogger(__name__)


def normalizar_rango_fechas(inicio_date, fin_date):
    if not fin_date or fin_date <= inicio_date:
        fin_date = inicio_date + timedelta(days=1)
    return inicio_date, fin_date


def calcular_metricas_tiempo(inicio_date, fin_date, hoy=None):
    hoy = hoy or timezone.localdate()
    inicio_date, fin_date = normalizar_rango_fechas(inicio_date, fin_date)

    duracion_total_dias = max((fin_date - inicio_date).days, 1)

    if hoy < inicio_date:
        return {
            'duracion_total_dias': duracion_total_dias,
            'dias_transcurridos': 0,
            'dias_restantes': duracion_total_dias,
            'progreso_temporal': 0,
            'esta_vencido': False,
        }

    if hoy >= fin_date:
        return {
            'duracion_total_dias': duracion_total_dias,
            'dias_transcurridos': duracion_total_dias,
            'dias_restantes': 0,
            'progreso_temporal': 100,
            'esta_vencido': True,
        }

    dias_transcurridos = max((hoy - inicio_date).days, 0)
    dias_restantes = max((fin_date - hoy).days, 0)
    progreso_temporal = int((dias_transcurridos / duracion_total_dias) * 100)

    return {
        'duracion_total_dias': duracion_total_dias,
        'dias_transcurridos': dias_transcurridos,
        'dias_restantes': dias_restantes,
        'progreso_temporal': max(0, min(progreso_temporal, 100)),
        'esta_vencido': False,
    }


def obtener_responsable_actividad(actividad):
    participante_responsable = actividad.participantes.filter(
        rol='RESPONSABLE'
    ).select_related('trabajador__user').first()

    if participante_responsable:
        return {
            'id': participante_responsable.trabajador_id,
            'nombre': str(participante_responsable.trabajador),
            'rol': participante_responsable.rol,
        }

    primer_participante = actividad.participantes.select_related('trabajador__user').first()

    if primer_participante:
        return {
            'id': primer_participante.trabajador_id,
            'nombre': str(primer_participante.trabajador),
            'rol': primer_participante.rol,
        }

    if getattr(actividad, 'creado_por', None):
        return {
            'id': actividad.creado_por.id,
            'nombre': actividad.creado_por.get_full_name() or actividad.creado_por.username,
            'rol': 'CREADOR',
        }

    return {
        'id': None,
        'nombre': 'Sin asignar',
        'rol': '',
    }


def obtener_responsable_ensayo(ensayo):
    return {
        'id': None,
        'nombre': 'Sin asignar',
        'rol': '',
    }


@login_required
@permiso_requerido('calendario.ver')
def calendario_dashboard(request):
    user = request.user
    ve_todos = ve_todos_los_ensayos(user)
    calendarios = [
        {
            'id': c.id,
            'nombre': c.nombre,
            'color': c.color if COLOR_HEX.match(c.color or '') else '#2563eb',
            'tipo': c.tipo,
            'miembros': c.num_miembros,
            'puede_crear': puede_crear_en(user, c),
        }
        for c in calendarios_visibles(user).annotate(num_miembros=Count('miembros'))
    ]
    trabajadores = [
        {'id': t.id, 'nombre': t.nombre_completo or t.user.get_username(), 'yo': t.user_id == user.id}
        for t in TrabajadorProfile.objects.select_related('user').filter(user__is_active=True)
        .order_by('nombre_completo')
    ]
    # Sin ensayos.ver_todos (técnico) no se listan razones sociales ni correos.
    clientes = list(
        Cliente.objects.order_by('razon_social').values('id', 'razon_social', 'correo_contacto')
    ) if ve_todos else []
    proyectos = list(
        Proyecto.objects.order_by('-fecha_inicio').values('id', 'codigo_proyecto', 'nombre_proyecto')[:300]
    )

    context = {
        'puede_correo': puede_entrar_correo(request.user),
        'datos_calendario': {
            'calendarios': calendarios,
            'trabajadores': trabajadores,
            'clientes': clientes,
            'proyectos': proyectos,
            'clases': CalendarioActividad.CLASE_ACTIVIDAD,
            'estados': CalendarioActividad.ESTADO_ACTIVIDAD,
            'prioridades': CalendarioActividad.PRIORIDAD,
            've_todos': ve_todos,
            'puede_crear': trabajador_tiene_permiso(user, 'calendario.crear'),
            'puede_editar': trabajador_tiene_permiso(user, 'calendario.editar'),
            'puede_eliminar': trabajador_tiene_permiso(user, 'calendario.eliminar'),
            'color_ensayos': COLOR_ENSAYOS,
        },
    }

    return render(request, 'actividades/calendario.html', context)


@login_required
@permiso_requerido('calendario.ver')
@require_GET
def calendario_eventos_json(request):
    ve_todos = ve_todos_los_ensayos(request.user)
    start = request.GET.get('start')
    end = request.GET.get('end')
    categoria_id = request.GET.get('categoria')
    estado = request.GET.get('estado')
    responsable_id = request.GET.get('responsable')
    proyecto_id = request.GET.get('proyecto')

    start_dt = parse_datetime(start) if start else None
    end_dt = parse_datetime(end) if end else None

    start_date = start_dt.date() if start_dt else None
    end_date = end_dt.date() if end_dt else None

    proyecto_obj = None
    cotizacion_id_proyecto = None

    if proyecto_id:
        proyecto_obj = Proyecto.objects.filter(pk=proyecto_id).select_related('cotizacion').first()
        if proyecto_obj and proyecto_obj.cotizacion_id:
            cotizacion_id_proyecto = proyecto_obj.cotizacion_id

    actividades = actividades_visibles(request.user).filter(
        es_visible=True
    ).select_related(
        'categoria',
        'cliente',
        'proyecto',
        'recepcion',
        'solicitud_ensayo',
        'informe_final'
    ).prefetch_related(
        'participantes__trabajador'
    )

    if start_dt:
        actividades = actividades.filter(fecha_fin__gte=start_dt)

    if end_dt:
        actividades = actividades.filter(fecha_inicio__lte=end_dt)

    if categoria_id:
        actividades = actividades.filter(categoria_id=categoria_id)

    if estado and estado.upper() in ['PROGRAMADA', 'EN_CURSO', 'COMPLETADA', 'CANCELADA', 'REPROGRAMADA', 'VENCIDA']:
        actividades = actividades.filter(estado=estado.upper())

    if responsable_id:
        actividades = actividades.filter(participantes__trabajador_id=responsable_id)

    if proyecto_id:
        actividades = actividades.filter(proyecto_id=proyecto_id)

    actividades = actividades.distinct().order_by('fecha_inicio')
    puede_editar = trabajador_tiene_permiso(request.user, 'calendario.editar')

    eventos = []

    for actividad in actividades:
        participantes = [
            {
                'nombre': str(p.trabajador),
                'rol': p.rol,
                'confirmado': p.confirmado,
            }
            for p in actividad.participantes.all()
        ]

        cliente_nombre = _cliente_visible(request.user, actividad, ve_todos)

        color = actividad.color_visual if COLOR_HEX.match(actividad.color_visual or '') else '#334155'
        eventos.append({
            'id': f'actividad-{actividad.id}',
            'title': actividad.titulo,
            'start': actividad.fecha_inicio.isoformat(),
            'end': actividad.fecha_fin.isoformat(),
            'allDay': actividad.todo_el_dia,
            'backgroundColor': color,
            'borderColor': color,
            'textColor': '#ffffff',
            'editable': bool(puede_editar and actividad.permite_edicion_manual
                             and puede_crear_en(request.user, actividad.categoria)),
            'extendedProps': {
                'tipo': 'actividad',
                'actividad_id': actividad.id,
                'calendario_id': actividad.categoria_id or 0,
                'color': color,
                'participo': any(p.trabajador.user_id == request.user.id for p in actividad.participantes.all()),
                'mio': actividad.creado_por_id == request.user.id,
                'clase': actividad.clase,
                'estado': actividad.estado,
                'prioridad': actividad.prioridad,
                'descripcion': actividad.descripcion or '',
                'ubicacion': actividad.ubicacion or '',
                'cliente': cliente_nombre,
                'proyecto': actividad.proyecto.nombre_proyecto if actividad.proyecto else '',
                'proyecto_codigo': actividad.proyecto.codigo_proyecto if actividad.proyecto else '',
                'es_automatica': actividad.es_automatica,
                'bloquea_agenda': actividad.bloquea_agenda,
                'permite_edicion_manual': actividad.permite_edicion_manual,
                'categoria': actividad.categoria.nombre if actividad.categoria else '',
                'participantes': participantes,
                'responsable': participantes[0]['nombre'] if participantes else 'Sin asignar',
                'fecha_inicio_real': actividad.fecha_inicio.isoformat() if actividad.fecha_inicio else '',
                'fecha_fin_real': actividad.fecha_fin.isoformat() if actividad.fecha_fin else '',
                'calendar_style': 'standard',
                'codigo_solicitud': '',
                'muestra': '',
                'servicio': '',
                'render_hint': 'standard',
            }
        })

    detalles_ensayo = DetalleSolicitudEnsayo.objects.select_related(
        'solicitud',
        'solicitud__cotizacion',
        'solicitud__cotizacion__cliente',
        'muestra',
        'servicio_cotizado',
        'servicio_cotizado__servicio',
        'tecnico_asignado'
    ).order_by('solicitud__fecha_solicitud', 'id')

    if cotizacion_id_proyecto:
        detalles_ensayo = detalles_ensayo.filter(
            solicitud__cotizacion_id=cotizacion_id_proyecto
        )

    if start_date:
        detalles_ensayo = detalles_ensayo.filter(
            solicitud__fecha_solicitud__gte=start_date
        )

    if end_date:
        detalles_ensayo = detalles_ensayo.filter(
            solicitud__fecha_solicitud__lte=end_date
        )

    if estado:
        estado_lower = estado.lower()
        if estado_lower in ['pendiente', 'proceso', 'finalizado']:
            detalles_ensayo = detalles_ensayo.filter(
                solicitud__estado=estado_lower
            )

    if responsable_id:
        detalles_ensayo = detalles_ensayo.filter(
            tecnico_asignado_id=responsable_id
        )

    if not ve_todos:
        detalles_ensayo = detalles_ensayo.filter(tecnico_asignado__user=request.user)

    colores_ensayos = {
        'pendiente': '#94a3b8',
        'proceso': '#f59e0b',
        'finalizado': '#10b981',
    }

    for detalle in detalles_ensayo:
        solicitud = detalle.solicitud

        if not solicitud or not solicitud.fecha_solicitud:
            continue

        fecha_registro = solicitud.fecha_solicitud
        fecha_entrega = detalle.fecha_entrega_programada or fecha_registro

        cliente_nombre = ''

        if solicitud.cotizacion and solicitud.cotizacion.cliente:
            cliente_nombre = nombre_cliente_visible(request.user, solicitud.cotizacion.cliente, ve_todos)

        codigo_solicitud = solicitud.codigo_solicitud if solicitud else f'DET-{detalle.id}'
        muestra_codigo = detalle.muestra.codigo_laboratorio if detalle.muestra else 'Sin muestra'

        if detalle.servicio_cotizado and detalle.servicio_cotizado.servicio:
            servicio_nombre = detalle.servicio_cotizado.servicio.nombre
        else:
            servicio_nombre = detalle.descripcion_ensayo or 'Ensayo'

        tecnico_nombre = detalle.tecnico_asignado.nombre_completo if detalle.tecnico_asignado else 'Sin asignar'
        estado_val = (solicitud.estado or 'pendiente').lower()
        color = colores_ensayos.get(estado_val, '#94a3b8')

        titulo_evento = f'{muestra_codigo} · {servicio_nombre}'

        if len(titulo_evento) > 60:
            titulo_evento = titulo_evento[:57] + '...'

        # Van en la fila «todo el día»: no tienen hora y en la grilla tapaban
        # las reuniones de las 8:00.
        eventos.append({
            'id': f'ensayo-detalle-{detalle.id}',
            'title': titulo_evento,
            'start': fecha_registro.isoformat(),
            'allDay': True,
            'editable': False,
            'backgroundColor': COLOR_ENSAYOS,
            'borderColor': COLOR_ENSAYOS,
            'textColor': '#ffffff',
            'extendedProps': {
                'tipo': 'ensayo',
                'calendario_id': CALENDARIO_ENSAYOS,
                'color': COLOR_ENSAYOS,
                'color_estado': color,
                'clase': 'ENSAYO',
                'estado': estado_val.upper(),
                'descripcion': detalle.descripcion_ensayo or servicio_nombre,
                'cliente': cliente_nombre,
                'proyecto': proyecto_obj.nombre_proyecto if proyecto_obj else '',
                'proyecto_codigo': proyecto_obj.codigo_proyecto if proyecto_obj else '',
                'responsable': tecnico_nombre,
                'codigo_solicitud': codigo_solicitud,
                'muestra': muestra_codigo,
                'servicio': servicio_nombre,
                'tecnico_id': detalle.tecnico_asignado_id,
                'detalle_id': detalle.id,
                'solicitud_id': solicitud.id if solicitud else None,
                'fecha_inicio_real': f'{fecha_registro.isoformat()}T08:00:00',
                'fecha_fin_real': f'{fecha_entrega.isoformat()}T18:00:00',
                'fecha_entrega_programada': f'{fecha_entrega.isoformat()}T18:00:00',
                'calendar_style': 'start_only',
                'render_hint': 'dot_label',
                'mostrar_solo_inicio': True,
            }
        })

    return JsonResponse(eventos, safe=False)


@login_required
@permiso_requerido('calendario.ver')
@require_GET
def calendario_actividad_detalle_json(request, pk):
    ve_todos = ve_todos_los_ensayos(request.user)
    actividad = get_object_or_404(
        actividades_visibles(request.user).select_related(
            'creado_por',
            'categoria',
            'cliente',
            'proyecto',
            'recepcion',
            'solicitud_ensayo',
            'informe_final'
        ).prefetch_related(
            'participantes__trabajador',
            'recordatorios'
        ),
        pk=pk
    )

    data = {
        'id': actividad.id,
        'titulo': actividad.titulo,
        'descripcion': actividad.descripcion or '',
        'tipo': actividad.tipo,
        'clase': actividad.clase,
        'estado': actividad.estado,
        'prioridad': actividad.prioridad,
        'fecha_inicio': actividad.fecha_inicio.isoformat(),
        'fecha_fin': actividad.fecha_fin.isoformat(),
        'todo_el_dia': actividad.todo_el_dia,
        'bloquea_agenda': actividad.bloquea_agenda,
        'es_visible': actividad.es_visible,
        'es_automatica': actividad.es_automatica,
        'permite_edicion_manual': actividad.permite_edicion_manual,
        'ubicacion': actividad.ubicacion or '',
        'enlace_externo': actividad.enlace_externo or '',
        'observaciones': actividad.observaciones or '',
        'cliente_id': actividad.cliente_id,
        'cliente_nombre_manual': actividad.cliente_nombre_manual or '',
        'proyecto_id': actividad.proyecto_id,
        'recepcion_id': actividad.recepcion_id,
        'solicitud_ensayo_id': actividad.solicitud_ensayo_id,
        'informe_final_id': actividad.informe_final_id,
        'categoria_id': actividad.categoria_id,
        'calendario_nombre': actividad.categoria.nombre if actividad.categoria else '',
        'color_visual': actividad.color_visual,
        'cliente_nombre': _cliente_visible(request.user, actividad, ve_todos),
        'cliente_tiene_correo': bool(actividad.cliente and actividad.cliente.correo_contacto and ve_todos),
        'aviso_cliente_enviado_en': (
            actividad.aviso_cliente_enviado_en.isoformat() if actividad.aviso_cliente_enviado_en else ''
        ),
        'proyecto_nombre': (
            f'{actividad.proyecto.codigo_proyecto} · {actividad.proyecto.nombre_proyecto}' if actividad.proyecto else ''
        ),
        'creado_por': (actividad.creado_por.get_full_name() or actividad.creado_por.get_username()),
        'puede_editar': bool(
            trabajador_tiene_permiso(request.user, 'calendario.editar')
            and puede_crear_en(request.user, actividad.categoria)
            and (actividad.permite_edicion_manual or not actividad.es_automatica)
        ),
        'puede_eliminar': bool(
            trabajador_tiene_permiso(request.user, 'calendario.eliminar')
            and puede_crear_en(request.user, actividad.categoria)
        ),
        'participantes': [
            {
                'trabajador_id': p.trabajador_id,
                'nombre': p.trabajador.nombre_completo or str(p.trabajador),
                'rol': p.rol,
                'confirmado': p.confirmado,
                'comentario': p.comentario or '',
            }
            for p in actividad.participantes.all()
        ],
        'recordatorios': [
            {
                'id': r.id,
                'minutos_antes': r.minutos_antes,
                'tipo': r.tipo,
                'enviado': r.enviado,
            }
            for r in actividad.recordatorios.all()
        ]
    }

    return JsonResponse(data)


@login_required
@require_POST
def calendario_actividad_guardar_json(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        actividad_id = payload.get('id')

        if actividad_id:
            if not trabajador_tiene_permiso(request.user, 'calendario.editar'):
                return JsonResponse({
                    'success': False,
                    'error': 'No tienes permiso para editar actividades.'
                }, status=403)
        else:
            if not trabajador_tiene_permiso(request.user, 'calendario.crear'):
                return JsonResponse({
                    'success': False,
                    'error': 'No tienes permiso para crear actividades.'
                }, status=403)

        if actividad_id:
            try:
                actividad_id = int(actividad_id)

                if actividad_id <= 0:
                    raise ValueError

            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'ID de actividad inválido.'}, status=400)

        if actividad_id:
            actividad = get_object_or_404(actividades_visibles(request.user), pk=actividad_id)

            if not puede_crear_en(request.user, actividad.categoria):
                return JsonResponse({
                    'success': False,
                    'error': 'No puedes editar eventos de ese calendario.'
                }, status=403)

            if actividad.es_automatica and not actividad.permite_edicion_manual:
                return JsonResponse({
                    'success': False,
                    'error': 'Esta actividad automática no permite edición manual.'
                }, status=400)
        else:
            actividad = CalendarioActividad(
                creado_por=request.user,
                tipo='MANUAL',
                es_automatica=False,
            )

        titulo = (payload.get('titulo') or '').strip()

        if not titulo or len(titulo) < 2 or len(titulo) > 200:
            return JsonResponse({'success': False, 'error': 'El título debe tener entre 2 y 200 caracteres.'}, status=400)

        if re.search(r'[<>]', titulo):
            logger.warning(f"Intento de XSS en calendario_actividad_guardar_json por usuario {request.user.username}")
            return JsonResponse({'success': False, 'error': 'Caracteres no permitidos detectados en el título.'}, status=400)

        descripcion = (payload.get('descripcion') or '').strip()

        if len(descripcion) > 1000:
            return JsonResponse({'success': False, 'error': 'La descripción no puede exceder 1000 caracteres.'}, status=400)

        if re.search(r'[<>]', descripcion):
            logger.warning(f"Intento de XSS en calendario_actividad_guardar_json por usuario {request.user.username}")
            return JsonResponse({'success': False, 'error': 'Caracteres no permitidos detectados en la descripción.'}, status=400)

        fecha_inicio = parse_datetime(payload.get('fecha_inicio') or '')
        fecha_fin = parse_datetime(payload.get('fecha_fin') or '')

        if not fecha_inicio or not fecha_fin:
            return JsonResponse({'success': False, 'error': 'Fechas inválidas.'}, status=400)

        if fecha_fin < fecha_inicio:
            return JsonResponse({'success': False, 'error': 'La fecha de fin no puede ser anterior a la de inicio.'}, status=400)

        cliente_id = payload.get('cliente_id') or None
        cliente_nombre_manual = (payload.get('cliente_nombre_manual') or '').strip()
        proyecto_id = payload.get('proyecto_id') or None
        clase = payload.get('clase') or 'OTRO'

        # El cliente es opcional: sin cliente es una actividad interna.
        cliente = None
        if cliente_id:
            if not ve_todos_los_ensayos(request.user):
                return JsonResponse({'success': False, 'error': 'No puedes vincular clientes.'}, status=403)
            cliente = Cliente.objects.filter(pk=cliente_id).first()
            if cliente is None:
                return JsonResponse({'success': False, 'error': 'El cliente no existe.'}, status=400)

        avisar_cliente = bool(payload.get('avisar_cliente'))
        if avisar_cliente and (cliente is None or not cliente.correo_contacto):
            return JsonResponse({
                'success': False,
                'error': 'Para enviar el aviso, elige un cliente con correo registrado.'
            }, status=400)

        calendario = None
        calendario_id = payload.get('categoria_id') or None
        if calendario_id:
            calendario = calendarios_visibles(request.user).filter(pk=calendario_id).first()
            if calendario is None:
                return JsonResponse({'success': False, 'error': 'Calendario no válido.'}, status=400)
        if not puede_crear_en(request.user, calendario):
            return JsonResponse({
                'success': False,
                'error': 'No puedes crear eventos en ese calendario.'
            }, status=403)

        if len(cliente_nombre_manual) > 255:
            return JsonResponse({
                'success': False,
                'error': 'El nombre del cliente no puede exceder 255 caracteres.'
            }, status=400)

        if re.search(r'[<>]', cliente_nombre_manual):
            logger.warning(f"Intento de XSS en cliente_nombre_manual por usuario {request.user.username}")
            return JsonResponse({
                'success': False,
                'error': 'Caracteres no permitidos detectados en el nombre del cliente.'
            }, status=400)

        if clase == 'ENSAYO' and not proyecto_id:
            return JsonResponse({
                'success': False,
                'error': 'El proyecto es obligatorio para actividades de tipo ensayo.'
            }, status=400)

        estado = payload.get('estado') or 'PROGRAMADA'
        prioridad = payload.get('prioridad') or 'MEDIA'
        if (clase not in dict(CalendarioActividad.CLASE_ACTIVIDAD)
                or estado not in dict(CalendarioActividad.ESTADO_ACTIVIDAD)
                or prioridad not in dict(CalendarioActividad.PRIORIDAD)):
            return JsonResponse({'success': False, 'error': 'Clase, estado o prioridad no válidos.'}, status=400)

        recordatorios = payload.get('recordatorios') or []
        for r in recordatorios:
            minutos = r.get('minutos_antes')
            if minutos in [None, '']:
                continue
            try:
                if int(minutos) < 0:
                    raise ValueError
            except (TypeError, ValueError):
                return JsonResponse({'success': False, 'error': 'Los minutos del recordatorio deben ser un número entero positivo.'}, status=400)

        actividad.titulo = titulo
        actividad.descripcion = descripcion
        actividad.clase = clase
        actividad.estado = estado
        actividad.prioridad = prioridad
        actividad.fecha_inicio = fecha_inicio
        actividad.fecha_fin = fecha_fin
        actividad.todo_el_dia = bool(payload.get('todo_el_dia'))
        actividad.bloquea_agenda = bool(payload.get('bloquea_agenda'))
        actividad.es_visible = bool(payload.get('es_visible', True))
        actividad.ubicacion = payload.get('ubicacion') or ''
        actividad.enlace_externo = payload.get('enlace_externo') or ''
        actividad.observaciones = payload.get('observaciones') or ''
        actividad.actualizado_por = request.user

        actividad.categoria = calendario
        actividad.cliente = cliente
        actividad.cliente_nombre_manual = '' if cliente else (cliente_nombre_manual or ACTIVIDAD_INTERNA)
        actividad.proyecto_id = proyecto_id

        # Todo o nada: si falla un participante o recordatorio no queda
        # la actividad a medio guardar.
        with transaction.atomic():
            actividad.save()

            participantes = payload.get('participantes') or []

            actividad.participantes.all().delete()
            actividad.recordatorios.all().delete()

            participantes_bulk = []

            for p in participantes:
                trabajador_id = p.get('trabajador_id')

                if not trabajador_id:
                    continue

                participantes_bulk.append(
                    CalendarioParticipante(
                        actividad=actividad,
                        trabajador_id=trabajador_id,
                        rol=p.get('rol') or 'RESPONSABLE',
                        confirmado=bool(p.get('confirmado')),
                        comentario=p.get('comentario') or ''
                    )
                )

            if participantes_bulk:
                CalendarioParticipante.objects.bulk_create(participantes_bulk)

            recordatorios_bulk = []

            for r in recordatorios:
                minutos_antes = r.get('minutos_antes')

                if minutos_antes in [None, '']:
                    continue

                recordatorios_bulk.append(
                    CalendarioRecordatorio(
                        actividad=actividad,
                        minutos_antes=int(minutos_antes),
                        tipo=r.get('tipo') or 'APP'
                    )
                )

            if recordatorios_bulk:
                CalendarioRecordatorio.objects.bulk_create(recordatorios_bulk)

            if avisar_cliente:
                transaction.on_commit(lambda: enviar_aviso_cliente.delay(actividad.id))

        logger.info(f"Actividad guardada: {titulo} (ID: {actividad.id}) por usuario {request.user.username}")

        return JsonResponse({
            'success': True,
            'id': actividad.id,
            'aviso_cliente': avisar_cliente,
            'message': 'Actividad guardada correctamente.'
        })

    except ValueError as e:
        logger.warning(f"Error de validación en calendario_actividad_guardar_json por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error interno en calendario_actividad_guardar_json por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Error interno del servidor.'}, status=500)


@login_required
@permiso_requerido('calendario.eliminar')
@require_POST
def calendario_actividad_eliminar_json(request, pk):
    try:
        try:
            pk = int(pk)

            if pk <= 0:
                raise ValueError

        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'ID de actividad inválido.'}, status=400)

        actividad = get_object_or_404(actividades_visibles(request.user), pk=pk)

        if not puede_crear_en(request.user, actividad.categoria):
            return JsonResponse({'success': False, 'error': 'No puedes eliminar eventos de ese calendario.'}, status=403)

        if actividad.es_automatica and not actividad.permite_edicion_manual:
            return JsonResponse({
                'success': False,
                'error': 'Esta actividad automática no permite eliminación manual.'
            }, status=400)

        titulo = actividad.titulo
        actividad.delete()

        logger.info(f"Actividad eliminada: {titulo} (ID: {pk}) por usuario {request.user.username}")

        return JsonResponse({'success': True, 'message': 'Actividad eliminada correctamente.'})

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar actividad {pk} por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Error interno del servidor.'}, status=500)


@login_required
@permiso_requerido('calendario.ver')
@require_POST
def calendario_categoria_crear_json(request):
    """Crea un calendario. Uno personal lo crea cualquiera (solo para sí);
    uno de equipo pide calendario.crear. Si se eligen miembros, quien lo crea
    queda como miembro; sin miembros lo ven todos."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        nombre = (payload.get('nombre') or '').strip()
        color = (payload.get('color') or '#2563eb').strip()
        tipo = payload.get('tipo') or CalendarioCategoria.TIPO_PERSONAL

        if tipo not in dict(CalendarioCategoria.TIPOS):
            return JsonResponse({'success': False, 'error': 'Tipo de calendario no válido.'}, status=400)
        if not nombre or len(nombre) < 2 or len(nombre) > 100:
            return JsonResponse({'success': False, 'error': 'El nombre debe tener entre 2 y 100 caracteres.'}, status=400)
        if re.search(r'[<>]', nombre):
            return JsonResponse({'success': False, 'error': 'Caracteres no permitidos en el nombre.'}, status=400)
        if not COLOR_HEX.match(color):
            return JsonResponse({'success': False, 'error': 'Color no válido.'}, status=400)

        personal = tipo == CalendarioCategoria.TIPO_PERSONAL
        if not personal and not trabajador_tiene_permiso(request.user, 'calendario.crear'):
            return JsonResponse({'success': False, 'error': 'No puedes crear calendarios de equipo.'}, status=403)

        repetido = CalendarioCategoria.objects.filter(tipo=tipo, nombre__iexact=nombre)
        if personal:
            repetido = repetido.filter(propietario=request.user)
        if repetido.exists():
            return JsonResponse({'success': False, 'error': 'Ya existe un calendario con ese nombre.'}, status=400)

        miembros = []
        if not personal:
            ids = {int(i) for i in (payload.get('miembros') or []) if str(i).isdigit()}
            crean = {int(i) for i in (payload.get('miembros_crean') or []) if str(i).isdigit()}
            perfiles = TrabajadorProfile.objects.filter(pk__in=ids | crean).values_list('id', 'user_id')
            miembros = [(user_id, pid in crean) for pid, user_id in perfiles if user_id != request.user.id]

        with transaction.atomic():
            calendario = CalendarioCategoria.objects.create(
                nombre=nombre,
                color=color,
                tipo=tipo,
                propietario=request.user if personal else None,
                activo=True,
            )
            if miembros:
                CalendarioMiembro.objects.bulk_create(
                    [CalendarioMiembro(calendario=calendario, user=request.user, puede_crear=True)]
                    + [CalendarioMiembro(calendario=calendario, user_id=u, puede_crear=c) for u, c in miembros]
                )

        logger.info("Calendario %s creado (%s) por %s", calendario.pk, tipo, request.user.username)

        return JsonResponse({
            'success': True,
            'calendario': {
                'id': calendario.id,
                'nombre': calendario.nombre,
                'color': calendario.color,
                'tipo': calendario.tipo,
                'miembros': len(miembros) + 1 if miembros else 0,
                'puede_crear': True,
            },
        })

    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Datos no válidos.'}, status=400)
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error al crear calendario por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Error interno del servidor.'}, status=500)


@login_required
@permiso_requerido('calendario.editar')
@require_POST
def calendario_actividad_reprogramar_json(request, pk):
    try:
        try:
            pk = int(pk)

            if pk <= 0:
                raise ValueError

        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'ID de actividad inválido.'
            }, status=400)

        actividad = get_object_or_404(actividades_visibles(request.user), pk=pk)

        if not puede_crear_en(request.user, actividad.categoria):
            return JsonResponse({'success': False, 'error': 'No puedes mover eventos de ese calendario.'}, status=403)

        if actividad.es_automatica and not actividad.permite_edicion_manual:
            return JsonResponse({
                'success': False,
                'error': 'Esta actividad automática no permite reprogramación manual.'
            }, status=400)

        payload = json.loads(request.body.decode('utf-8'))

        fecha_inicio = parse_datetime(payload.get('fecha_inicio') or '')
        fecha_fin = parse_datetime(payload.get('fecha_fin') or '')

        if not fecha_inicio or not fecha_fin or fecha_fin < fecha_inicio:
            return JsonResponse({
                'success': False,
                'error': 'Fechas inválidas.'
            }, status=400)

        actividad.fecha_inicio = fecha_inicio
        if 'todo_el_dia' in payload:
            actividad.todo_el_dia = bool(payload.get('todo_el_dia'))
        actividad.fecha_fin = fecha_fin
        actividad.actualizado_por = request.user
        actividad.save()

        logger.info(f"Actividad reprogramada: {actividad.titulo} (ID: {pk}) por usuario {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': 'Actividad reprogramada correctamente.'
        })

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error al reprogramar actividad {pk} por usuario {request.user.username}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor.'
        }, status=500)


@login_required
@permiso_requerido('gantt.ver')
def gantt_dashboard(request):
    proyectos = Proyecto.objects.all().order_by('-fecha_inicio')
    categorias = calendarios_visibles(request.user)
    trabajadores = TrabajadorProfile.objects.select_related('user').all().order_by('user__username')

    context = {
        'proyectos': proyectos,
        'categorias': categorias,
        'trabajadores': trabajadores,
    }

    return render(request, 'actividades/gantt.html', context)


@login_required
@permiso_requerido('gantt.ver')
@require_GET
def gantt_actividades_json(request):
    ve_todos = ve_todos_los_ensayos(request.user)
    proyecto_id = request.GET.get('proyecto')
    estado = request.GET.get('estado')
    responsable_id = request.GET.get('responsable')
    incluir_ensayos = request.GET.get('ensayos', 'true').lower() == 'true'

    hoy_dt = timezone.now()
    hoy = timezone.localdate()
    hace_1_ano = hoy_dt - timedelta(days=365)
    hasta_1_ano = hoy_dt + timedelta(days=365)

    proyecto_obj = None
    cotizacion_id_proyecto = None

    if proyecto_id:
        proyecto_obj = Proyecto.objects.filter(pk=proyecto_id).select_related('cotizacion').first()

        if proyecto_obj and proyecto_obj.cotizacion_id:
            cotizacion_id_proyecto = proyecto_obj.cotizacion_id

    actividades = actividades_visibles(request.user).filter(
        es_visible=True,
        fecha_fin__gte=hace_1_ano,
        fecha_inicio__lte=hasta_1_ano,
    ).select_related(
        'categoria',
        'cliente',
        'proyecto',
        'recepcion',
        'solicitud_ensayo',
        'informe_final',
        'creado_por',
    ).prefetch_related(
        'participantes__trabajador__user'
    ).order_by('fecha_inicio', 'id')

    if proyecto_id:
        actividades = actividades.filter(proyecto_id=proyecto_id)

    if estado and estado.upper() in ['PROGRAMADA', 'EN_CURSO', 'COMPLETADA', 'CANCELADA', 'REPROGRAMADA', 'VENCIDA']:
        actividades = actividades.filter(estado=estado.upper())

    if responsable_id:
        actividades = actividades.filter(participantes__trabajador_id=responsable_id).distinct()

    data = []

    for actividad in actividades:
        inicio_date = actividad.fecha_inicio.date()
        fin_date = actividad.fecha_fin.date()
        inicio_date, fin_date = normalizar_rango_fechas(inicio_date, fin_date)

        metricas = calcular_metricas_tiempo(inicio_date, fin_date, hoy=hoy)
        responsable = obtener_responsable_actividad(actividad)

        estado_val = (actividad.estado or 'PROGRAMADA').upper()
        estado_css = estado_val.lower().replace('_', '-')

        data.append({
            'id': f'actividad-{actividad.id}',
            'db_id': actividad.id,
            'name': actividad.titulo,
            'start': inicio_date.strftime('%Y-%m-%d'),
            'end': fin_date.strftime('%Y-%m-%d'),
            'progress': metricas['progreso_temporal'],
            'progreso_temporal': metricas['progreso_temporal'],
            'duracion_total_dias': metricas['duracion_total_dias'],
            'dias_transcurridos': metricas['dias_transcurridos'],
            'dias_restantes': metricas['dias_restantes'],
            'esta_vencido': metricas['esta_vencido'] and estado_val not in ['COMPLETADA', 'CANCELADA'],
            'responsable': responsable['nombre'],
            'responsable_id': responsable['id'],
            'responsable_rol': responsable['rol'],
            'custom_class': f'estado-{estado_css}',
            'color': actividad.color_visual or '#2563eb',
            'estado': actividad.estado or 'PROGRAMADA',
            'clase': actividad.clase or 'OTRO',
            'proyecto': actividad.proyecto.nombre_proyecto if actividad.proyecto else '',
            'cliente': nombre_cliente_visible(request.user, actividad.cliente, ve_todos),
            'descripcion': actividad.descripcion or '',
            'tipo': 'actividad',
            'calendario_id': actividad.categoria_id,
            'calendario': actividad.categoria.nombre if actividad.categoria_id else 'Sin calendario',
            'calendario_color': (actividad.categoria.color if actividad.categoria_id else '') or actividad.color_visual or '#2563eb',
        })

    if incluir_ensayos:
        # HU-LIMS-22: estado y avance real por línea (actividades/gantt_ensayos.py).
        data.extend(lineas_de_ensayo(
            request.user, ve_todos, hoy,
            desde=hace_1_ano.date(), hasta=hasta_1_ano.date(),
            cotizacion_id=cotizacion_id_proyecto,
            responsable_id=responsable_id,
        ))

    data.sort(key=lambda x: (x['start'], x['name']))

    return JsonResponse(data, safe=False)