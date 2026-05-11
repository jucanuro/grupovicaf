import json
import logging
import re
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from clientes.models import Cliente
from proyectos.models import Proyecto, RecepcionMuestra, SolicitudEnsayo, InformeFinal, DetalleSolicitudEnsayo
from trabajadores.models import TrabajadorProfile
from trabajadores.permissions import permiso_requerido, trabajador_tiene_permiso

from .models import (
    CalendarioActividad,
    CalendarioCategoria,
    CalendarioParticipante,
    CalendarioRecordatorio,
)

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
    categorias = CalendarioCategoria.objects.filter(activo=True).order_by('nombre')
    trabajadores = TrabajadorProfile.objects.all().order_by('user__username')
    clientes = Cliente.objects.all().order_by('razon_social')
    proyectos = Proyecto.objects.all().order_by('-fecha_inicio')

    resumen = {
        'total_actividades': CalendarioActividad.objects.filter(es_visible=True).count(),
        'programadas': CalendarioActividad.objects.filter(es_visible=True, estado='PROGRAMADA').count(),
        'en_curso': CalendarioActividad.objects.filter(es_visible=True, estado='EN_CURSO').count(),
        'completadas': CalendarioActividad.objects.filter(es_visible=True, estado='COMPLETADA').count(),
        'vencidas': sum(1 for a in CalendarioActividad.objects.filter(es_visible=True) if a.esta_vencida),
        'automaticas': CalendarioActividad.objects.filter(es_visible=True, es_automatica=True).count(),
        'manuales': CalendarioActividad.objects.filter(es_visible=True, es_automatica=False).count(),
    }

    context = {
        'categorias': categorias,
        'trabajadores': trabajadores,
        'clientes': clientes,
        'proyectos': proyectos,
        'resumen': resumen,
        'clases_actividad': CalendarioActividad.CLASE_ACTIVIDAD,
        'estados_actividad': CalendarioActividad.ESTADO_ACTIVIDAD,
        'prioridades_actividad': CalendarioActividad.PRIORIDAD,
    }

    return render(request, 'actividades/calendario.html', context)


@login_required
@permiso_requerido('calendario.ver')
@require_GET
def calendario_eventos_json(request):
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

    actividades = CalendarioActividad.objects.filter(
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

        cliente_nombre = ''

        if actividad.cliente:
            cliente_nombre = actividad.cliente.razon_social
        else:
            cliente_nombre = actividad.cliente_nombre_manual or ''

        eventos.append({
            'id': f'actividad-{actividad.id}',
            'title': actividad.titulo,
            'start': actividad.fecha_inicio.isoformat(),
            'end': actividad.fecha_fin.isoformat(),
            'allDay': actividad.todo_el_dia,
            'backgroundColor': actividad.color_visual,
            'borderColor': actividad.color_visual,
            'textColor': '#ffffff',
            'extendedProps': {
                'tipo': 'actividad',
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
            cliente_nombre = solicitud.cotizacion.cliente.razon_social

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

        eventos.append({
            'id': f'ensayo-detalle-{detalle.id}',
            'title': titulo_evento,
            'start': f'{fecha_registro.isoformat()}T08:00:00',
            'allDay': False,
            'backgroundColor': color,
            'borderColor': color,
            'textColor': '#1e293b',
            'extendedProps': {
                'tipo': 'ensayo',
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
    actividad = get_object_or_404(
        CalendarioActividad.objects.select_related(
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
        'color_visual': actividad.color_visual,
        'participantes': [
            {
                'trabajador_id': p.trabajador_id,
                'nombre': str(p.trabajador),
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
            actividad = get_object_or_404(CalendarioActividad, pk=actividad_id)

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

        cliente_id = payload.get('cliente_id') or None
        cliente_nombre_manual = (payload.get('cliente_nombre_manual') or '').strip()
        proyecto_id = payload.get('proyecto_id') or None
        clase = payload.get('clase') or 'OTRO'

        if not cliente_id and not cliente_nombre_manual:
            return JsonResponse({
                'success': False,
                'error': 'Debes seleccionar un cliente o ingresar un nombre de cliente.'
            }, status=400)

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

        actividad.titulo = titulo
        actividad.descripcion = descripcion
        actividad.clase = clase
        actividad.estado = payload.get('estado') or 'PROGRAMADA'
        actividad.prioridad = payload.get('prioridad') or 'MEDIA'
        actividad.fecha_inicio = fecha_inicio
        actividad.fecha_fin = fecha_fin
        actividad.todo_el_dia = bool(payload.get('todo_el_dia'))
        actividad.bloquea_agenda = bool(payload.get('bloquea_agenda'))
        actividad.es_visible = bool(payload.get('es_visible', True))
        actividad.ubicacion = payload.get('ubicacion') or ''
        actividad.enlace_externo = payload.get('enlace_externo') or ''
        actividad.observaciones = payload.get('observaciones') or ''
        actividad.actualizado_por = request.user

        actividad.categoria_id = payload.get('categoria_id') or None
        actividad.cliente_id = cliente_id
        actividad.cliente_nombre_manual = '' if cliente_id else cliente_nombre_manual
        actividad.proyecto_id = proyecto_id

        actividad.save()

        participantes = payload.get('participantes') or []
        recordatorios = payload.get('recordatorios') or []

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

        logger.info(f"Actividad guardada: {titulo} (ID: {actividad.id}) por usuario {request.user.username}")

        return JsonResponse({
            'success': True,
            'id': actividad.id,
            'message': 'Actividad guardada correctamente.'
        })

    except ValueError as e:
        logger.warning(f"Error de validación en calendario_actividad_guardar_json por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

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

        actividad = get_object_or_404(CalendarioActividad, pk=pk)

        if actividad.es_automatica and not actividad.permite_edicion_manual:
            return JsonResponse({
                'success': False,
                'error': 'Esta actividad automática no permite eliminación manual.'
            }, status=400)

        titulo = actividad.titulo
        actividad.delete()

        logger.info(f"Actividad eliminada: {titulo} (ID: {pk}) por usuario {request.user.username}")

        return JsonResponse({'success': True, 'message': 'Actividad eliminada correctamente.'})

    except Exception as e:
        logger.error(f"Error al eliminar actividad {pk} por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Error interno del servidor.'}, status=500)


@login_required
@permiso_requerido('calendario.crear')
@require_POST
def calendario_categoria_crear_json(request):
    try:
        nombre = (request.POST.get('nombre') or '').strip()
        color = (request.POST.get('color') or '#2563eb').strip()
        icono = (request.POST.get('icono') or '').strip()

        if not nombre or len(nombre) < 2 or len(nombre) > 100:
            return JsonResponse({
                'success': False,
                'error': 'El nombre debe tener entre 2 y 100 caracteres.'
            }, status=400)

        if len(color) > 20:
            return JsonResponse({
                'success': False,
                'error': 'El color no puede exceder 20 caracteres.'
            }, status=400)

        if len(icono) > 50:
            return JsonResponse({
                'success': False,
                'error': 'El icono no puede exceder 50 caracteres.'
            }, status=400)

        if re.search(r'[<>]', nombre) or re.search(r'[<>]', color) or re.search(r'[<>]', icono):
            logger.warning(f"Intento de XSS en calendario_categoria_crear_json por usuario {request.user.username}")
            return JsonResponse({
                'success': False,
                'error': 'Caracteres no permitidos detectados.'
            }, status=400)

        if CalendarioCategoria.objects.filter(nombre__iexact=nombre).exists():
            return JsonResponse({
                'success': False,
                'error': 'Ya existe una categoría con ese nombre.'
            }, status=400)

        categoria = CalendarioCategoria.objects.create(
            nombre=nombre,
            color=color or '#2563eb',
            icono=icono or None,
            activo=True
        )

        logger.info(f"Categoría creada: {nombre} por usuario {request.user.username}")

        return JsonResponse({
            'success': True,
            'id': categoria.id,
            'nombre': categoria.nombre,
            'color': categoria.color,
            'icono': categoria.icono or '',
            'message': 'Categoría creada correctamente.'
        })

    except Exception as e:
        logger.error(f"Error al crear categoría por usuario {request.user.username}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor.'
        }, status=500)


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

        actividad = get_object_or_404(CalendarioActividad, pk=pk)

        if actividad.es_automatica and not actividad.permite_edicion_manual:
            return JsonResponse({
                'success': False,
                'error': 'Esta actividad automática no permite reprogramación manual.'
            }, status=400)

        payload = json.loads(request.body.decode('utf-8'))

        fecha_inicio = parse_datetime(payload.get('fecha_inicio') or '')
        fecha_fin = parse_datetime(payload.get('fecha_fin') or '')

        if not fecha_inicio or not fecha_fin:
            return JsonResponse({
                'success': False,
                'error': 'Fechas inválidas.'
            }, status=400)

        actividad.fecha_inicio = fecha_inicio
        actividad.fecha_fin = fecha_fin
        actividad.actualizado_por = request.user
        actividad.save()

        logger.info(f"Actividad reprogramada: {actividad.titulo} (ID: {pk}) por usuario {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': 'Actividad reprogramada correctamente.'
        })

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
    categorias = CalendarioCategoria.objects.filter(activo=True).order_by('nombre')
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

    actividades = CalendarioActividad.objects.filter(
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
            'cliente': actividad.cliente.razon_social if actividad.cliente else '',
            'descripcion': actividad.descripcion or '',
            'tipo': 'actividad',
        })

    if incluir_ensayos:
        detalles_ensayo = DetalleSolicitudEnsayo.objects.filter(
            solicitud__fecha_solicitud__gte=hace_1_ano.date(),
            solicitud__fecha_solicitud__lte=hasta_1_ano.date(),
        ).select_related(
            'solicitud',
            'solicitud__cotizacion',
            'solicitud__cotizacion__cliente',
            'muestra',
            'servicio_cotizado',
            'servicio_cotizado__servicio',
            'tecnico_asignado',
        ).order_by('solicitud__fecha_solicitud', 'id')

        if cotizacion_id_proyecto:
            detalles_ensayo = detalles_ensayo.filter(solicitud__cotizacion_id=cotizacion_id_proyecto)

        if estado:
            estado_lower = estado.lower()

            if estado_lower in ['pendiente', 'proceso', 'finalizado']:
                detalles_ensayo = detalles_ensayo.filter(solicitud__estado=estado_lower)

            elif estado.upper() in ['PROGRAMADA', 'EN_CURSO', 'COMPLETADA', 'CANCELADA', 'REPROGRAMADA', 'VENCIDA']:
                detalles_ensayo = detalles_ensayo.none()

        if responsable_id:
            detalles_ensayo = detalles_ensayo.filter(tecnico_asignado_id=responsable_id)

        colores_ensayos = {
            'pendiente': '#94a3b8',
            'proceso': '#f59e0b',
            'finalizado': '#10b981',
        }

        for detalle in detalles_ensayo:
            solicitud = detalle.solicitud
            inicio_date = solicitud.fecha_solicitud if solicitud and solicitud.fecha_solicitud else hoy
            fin_date = detalle.fecha_entrega_programada or inicio_date
            inicio_date, fin_date = normalizar_rango_fechas(inicio_date, fin_date)

            metricas = calcular_metricas_tiempo(inicio_date, fin_date, hoy=hoy)

            estado_val = (solicitud.estado or 'pendiente').lower()
            color = colores_ensayos.get(estado_val, '#94a3b8')

            cliente_nombre = ''

            if solicitud and solicitud.cotizacion and solicitud.cotizacion.cliente:
                cliente_nombre = solicitud.cotizacion.cliente.razon_social

            muestra_codigo = detalle.muestra.codigo_laboratorio if detalle.muestra else 'Sin muestra'

            if detalle.servicio_cotizado and detalle.servicio_cotizado.servicio:
                servicio_nombre = detalle.servicio_cotizado.servicio.nombre
            else:
                servicio_nombre = detalle.descripcion_ensayo or 'Ensayo'

            responsable_nombre = detalle.tecnico_asignado.nombre_completo if detalle.tecnico_asignado else 'Sin asignar'

            codigo_solicitud = solicitud.codigo_solicitud if solicitud else f'DET-{detalle.id}'
            nombre_barra = f'{codigo_solicitud} | {muestra_codigo} | {servicio_nombre}'

            data.append({
                'id': f'ensayo-detalle-{detalle.id}',
                'db_id': detalle.id,
                'solicitud_id': solicitud.id if solicitud else None,
                'name': nombre_barra[:140],
                'start': inicio_date.strftime('%Y-%m-%d'),
                'end': fin_date.strftime('%Y-%m-%d'),
                'progress': metricas['progreso_temporal'],
                'progreso_temporal': metricas['progreso_temporal'],
                'duracion_total_dias': metricas['duracion_total_dias'],
                'dias_transcurridos': metricas['dias_transcurridos'],
                'dias_restantes': metricas['dias_restantes'],
                'esta_vencido': metricas['esta_vencido'] and estado_val != 'finalizado',
                'responsable': responsable_nombre,
                'responsable_id': detalle.tecnico_asignado_id,
                'responsable_rol': 'TÉCNICO',
                'custom_class': f'estado-{estado_val}',
                'color': color,
                'estado': estado_val.upper(),
                'clase': 'ENSAYO',
                'proyecto': proyecto_obj.nombre_proyecto if proyecto_obj else '',
                'cliente': cliente_nombre,
                'descripcion': detalle.descripcion_ensayo or servicio_nombre,
                'tipo': 'ensayo',
                'muestra': muestra_codigo,
                'servicio': servicio_nombre,
                'codigo_solicitud': codigo_solicitud,
            })

    data.sort(key=lambda x: (x['start'], x['name']))

    return JsonResponse(data, safe=False)