import json
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from clientes.models import Cliente
from trabajadores.models import TrabajadorProfile
from proyectos.models import Proyecto, RecepcionMuestra, SolicitudEnsayo, InformeFinal

from .models import (
    CalendarioActividad,
    CalendarioCategoria,
    CalendarioParticipante,
    CalendarioRecordatorio,
)


@login_required
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
@require_GET
def calendario_eventos_json(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    categoria_id = request.GET.get('categoria')
    estado = request.GET.get('estado')
    responsable_id = request.GET.get('responsable')

    actividades = CalendarioActividad.objects.filter(es_visible=True).select_related(
        'categoria', 'cliente', 'proyecto', 'recepcion', 'solicitud_ensayo', 'informe_final'
    ).prefetch_related('participantes__trabajador')

    if start:
        start_dt = parse_datetime(start)
        if start_dt:
            actividades = actividades.filter(fecha_fin__gte=start_dt)

    if end:
        end_dt = parse_datetime(end)
        if end_dt:
            actividades = actividades.filter(fecha_inicio__lte=end_dt)

    if categoria_id:
        actividades = actividades.filter(categoria_id=categoria_id)

    if estado:
        actividades = actividades.filter(estado=estado)

    if responsable_id:
        actividades = actividades.filter(participantes__trabajador_id=responsable_id)

    actividades = actividades.distinct().order_by('fecha_inicio')

    eventos = []
    for actividad in actividades:
        eventos.append({
            'id': actividad.id,
            'title': actividad.titulo,
            'start': actividad.fecha_inicio.isoformat(),
            'end': actividad.fecha_fin.isoformat(),
            'allDay': actividad.todo_el_dia,
            'backgroundColor': actividad.color_visual,
            'borderColor': actividad.color_visual,
            'textColor': '#ffffff',
            'extendedProps': {
                'descripcion': actividad.descripcion or '',
                'tipo': actividad.tipo,
                'clase': actividad.clase,
                'estado': actividad.estado,
                'prioridad': actividad.prioridad,
                'ubicacion': actividad.ubicacion or '',
                'cliente': actividad.cliente.razon_social if actividad.cliente else '',
                'proyecto': actividad.proyecto.nombre_proyecto if actividad.proyecto else '',
                'proyecto_codigo': actividad.proyecto.codigo_proyecto if actividad.proyecto else '',
                'es_automatica': actividad.es_automatica,
                'bloquea_agenda': actividad.bloquea_agenda,
                'permite_edicion_manual': actividad.permite_edicion_manual,
                'categoria': actividad.categoria.nombre if actividad.categoria else '',
                'participantes': [
                    {
                        'nombre': str(p.trabajador),
                        'rol': p.rol,
                        'confirmado': p.confirmado,
                    }
                    for p in actividad.participantes.all()
                ]
            }
        })

    return JsonResponse(eventos, safe=False)


@login_required
@require_GET
def calendario_actividad_detalle_json(request, pk):
    actividad = get_object_or_404(
        CalendarioActividad.objects.select_related(
            'categoria', 'cliente', 'proyecto', 'recepcion', 'solicitud_ensayo', 'informe_final'
        ).prefetch_related('participantes__trabajador', 'recordatorios'),
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
        if not titulo:
            return JsonResponse({'success': False, 'error': 'El título es obligatorio.'}, status=400)

        fecha_inicio = parse_datetime(payload.get('fecha_inicio') or '')
        fecha_fin = parse_datetime(payload.get('fecha_fin') or '')

        if not fecha_inicio or not fecha_fin:
            return JsonResponse({'success': False, 'error': 'Fechas inválidas.'}, status=400)

        actividad.titulo = titulo
        actividad.descripcion = payload.get('descripcion') or ''
        actividad.clase = payload.get('clase') or 'OTRO'
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
        actividad.cliente_id = payload.get('cliente_id') or None
        actividad.proyecto_id = payload.get('proyecto_id') or None

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

        return JsonResponse({
            'success': True,
            'id': actividad.id,
            'message': 'Actividad guardada correctamente.'
        })

    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)


@login_required
@require_POST
def calendario_actividad_eliminar_json(request, pk):
    try:
        actividad = get_object_or_404(CalendarioActividad, pk=pk)

        if actividad.es_automatica and not actividad.permite_edicion_manual:
            return JsonResponse({
                'success': False,
                'error': 'Esta actividad automática no permite eliminación manual.'
            }, status=400)

        actividad.delete()
        return JsonResponse({'success': True, 'message': 'Actividad eliminada correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def calendario_categoria_crear_json(request):
    try:
        nombre = (request.POST.get('nombre') or '').strip()
        color = (request.POST.get('color') or '#2563eb').strip()
        icono = (request.POST.get('icono') or '').strip()

        if not nombre:
            return JsonResponse({
                'success': False,
                'error': 'El nombre es obligatorio.'
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

        return JsonResponse({
            'success': True,
            'id': categoria.id,
            'nombre': categoria.nombre,
            'color': categoria.color,
            'icono': categoria.icono or '',
            'message': 'Categoría creada correctamente.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=500)


@login_required
@require_POST
def calendario_actividad_reprogramar_json(request, pk):
    try:
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

        return JsonResponse({
            'success': True,
            'message': 'Actividad reprogramada correctamente.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



@login_required
def gantt_dashboard(request):
    proyectos = Proyecto.objects.all().order_by('-fecha_inicio')
    categorias = CalendarioCategoria.objects.filter(activo=True).order_by('nombre')

    context = {
        'proyectos': proyectos,
        'categorias': categorias,
    }
    return render(request, 'actividades/gantt.html', context)


@login_required
@require_GET
def gantt_actividades_json(request):
    proyecto_id = request.GET.get('proyecto')
    categoria_id = request.GET.get('categoria')
    estado = request.GET.get('estado')

    hoy = timezone.now()
    hace_1_ano = hoy - timedelta(days=365)
    hasta_1_ano = hoy + timedelta(days=365)

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
    ).order_by('fecha_inicio', 'id')

    if proyecto_id:
        actividades = actividades.filter(proyecto_id=proyecto_id)

    if categoria_id:
        actividades = actividades.filter(categoria_id=categoria_id)

    if estado:
        actividades = actividades.filter(estado=estado)

    progress_map = {
        'PROGRAMADA': 20,
        'EN_CURSO': 65,
        'COMPLETADA': 100,
        'CANCELADA': 100,
        'REPROGRAMADA': 35,
        'VENCIDA': 100,
    }

    data = []

    for actividad in actividades:
        inicio_date = actividad.fecha_inicio.date()
        fin_date = actividad.fecha_fin.date()

        if fin_date <= inicio_date:
            fin_date = inicio_date + timedelta(days=1)

        estado_val = (actividad.estado or 'PROGRAMADA').upper()
        estado_css = estado_val.lower().replace('_', '-')

        color = actividad.color_visual or '#2563eb'
        progress = progress_map.get(estado_val, 0)

        data.append({
            'id': f'actividad-{actividad.id}',
            'name': actividad.titulo,
            'start': inicio_date.strftime('%Y-%m-%d'),
            'end': fin_date.strftime('%Y-%m-%d'),
            'progress': progress,
            'custom_class': f'estado-{estado_css}',
            'color': color,
            'estado': actividad.estado,
            'clase': actividad.clase,
            'proyecto': actividad.proyecto.nombre_proyecto if actividad.proyecto else '',
            'cliente': actividad.cliente.razon_social if actividad.cliente else '',
            'descripcion': actividad.descripcion or '',
        })

    return JsonResponse(data, safe=False)