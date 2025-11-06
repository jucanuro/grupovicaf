# /home/jucanuro/projects/grupovicaf/proyectos/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
import json
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.db import IntegrityError
from django.utils import timezone
from .models import Proyecto, SolicitudEnsayo,DetalleEnsayo, Muestra,TipoEnsayo, AsignacionTipoEnsayo, ReporteIncidencia
from clientes.models import Cliente as Cliente 
from servicios.models import Cotizacion,CotizacionDetalle, Norma, Metodo
from trabajadores.models import TrabajadorProfile

try:
    from .models import ResultadoEnsayo 
except ImportError:

    class ResultadoEnsayo:
        DoesNotExist = Exception 
        pass 
# ----------------------------------------------------------------------------------

@login_required
def lista_proyectos_pendientes(request): 
    """
    Vista modificada para cargar TODOS los proyectos sin importar su estado.
    """
    proyectos = Proyecto.objects.all().order_by('-creado_en')
    
    context = {
        'proyectos_pendientes': proyectos, 
        'titulo_lista': 'Todos los Proyectos para Gestión', 
    }
    
    return render(request, 'proyectos/lista_proyectos_pendientes.html', context)


@csrf_exempt
def editar_proyecto_view(request, pk):
    """
    Vista para editar un proyecto existente.
    Maneja las solicitudes POST desde el modal de edición.
    """
    if request.method == 'POST':
        try:
            proyecto = get_object_or_404(Proyecto, pk=pk)
            data = json.loads(request.body)
            proyecto.nombre_proyecto = data.get('nombre', proyecto.nombre_proyecto)
            proyecto.estado = data.get('estado', proyecto.estado)
            proyecto.monto_cotizacion = data.get('monto', proyecto.monto_cotizacion)
            proyecto.save()
            return JsonResponse({'success': True, 'message': 'Proyecto actualizado con éxito.'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Formato JSON inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Método no permitido.'}, status=405)


def get_date_or_none(date_string):
    """Convierte una cadena de fecha a formato YYYY-MM-DD o None si está vacía."""
    return date_string if date_string else None


@csrf_exempt
def crear_muestra(request): 
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método de solicitud no permitido.'}, status=405)

    try:
        data = json.loads(request.body)
        proyecto_id = data.get('proyecto_id')

        # 1. Validaciones
        if not proyecto_id:
            return JsonResponse({'status': 'error', 'message': 'El ID del proyecto no puede ser nulo.'}, status=400)

        try:
            proyecto = Proyecto.objects.get(id=proyecto_id)
        except Proyecto.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'El proyecto no existe.'}, status=404)

        codigo_muestra = data.get('codigo_muestra')
        if Muestra.objects.filter(proyecto=proyecto, codigo_muestra=codigo_muestra).exists():
            return JsonResponse({'status': 'error', 'message': f'Ya existe una muestra con el código "{codigo_muestra}" para este proyecto.'}, status=400)

        with transaction.atomic():
            # 2. Creación de Muestra
            muestra = Muestra.objects.create(
                proyecto=proyecto,
                codigo_muestra=codigo_muestra,
                descripcion_muestra=data.get('descripcion_muestra', ''),
                id_lab=data.get('id_lab'),
                tipo_muestra=data.get('tipo_muestra'),
                masa_aprox_kg=data.get('masa_aprox_kg'),
                fecha_recepcion=get_date_or_none(data.get('fecha_recepcion')),
                fecha_fabricacion=get_date_or_none(data.get('fecha_fabricacion')),
                fecha_ensayo_rotura=get_date_or_none(data.get('fecha_ensayo_rotura')),
                # El estado inicial debe ser 'RECIBIDA' según tu modelo Muestra.ESTADOS_MUESTRA
                estado=data.get('estado', 'RECIBIDA'), 
            )
            
            # 3. Creación de Solicitud de Ensayo (vinculada a la Muestra)
            # El código de solicitud podría ser un correlativo, o basarse en la muestra y el proyecto.
            codigo_solicitud = f"OE-{proyecto.codigo_proyecto}-{codigo_muestra}" 

            solicitud_ensayo = SolicitudEnsayo.objects.create(
                muestra=muestra,
                codigo_solicitud=codigo_solicitud,
                fecha_solicitud=timezone.now().date(),
                # generada_por=request.user.trabajadorprofile, # Asumir que el usuario logueado es el generador
                estado='ASIGNADA' # Estado inicial según tu modelo SolicitudEnsayo.ESTADOS_SOLICITUD
            )

            # 4. Lógica de Actualización del Proyecto
            proyecto.numero_muestras_registradas = Muestra.objects.filter(proyecto=proyecto).count()
            if proyecto.estado == 'PENDIENTE':
                proyecto.estado = 'EN_CURSO'
            proyecto.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Muestra {muestra.codigo_muestra} y Solicitud de Ensayo ({solicitud_ensayo.codigo_solicitud}) creadas correctamente.',
            'muestra': {
                'id': muestra.pk,
                'codigo_muestra': muestra.codigo_muestra,
                'tipo_muestra': muestra.tipo_muestra,
                'estado': muestra.estado,
                'solicitud_id': solicitud_ensayo.id
            }
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
    except Exception as e:
        # En producción, usa logging.error(e)
        return JsonResponse({'status': 'error', 'message': f'Error interno: {str(e)}'}, status=500)


@require_GET
def muestras_del_proyecto(request, proyecto_id):
    """
    Devuelve la lista de muestras para un proyecto específico en formato JSON.
    """
    try:
        # 1. Obtención de datos optimizada:
        # Usamos select_related para obtener la SolicitudEnsayo en la misma consulta
        muestras = Muestra.objects.filter(proyecto_id=proyecto_id).order_by('-creado_en')
        
        muestras_list = []
        for muestra in muestras:
            # Manejo seguro de la relación OneToOne (solicitud_ensayo)
            solicitud_id = None
            try:
                solicitud_id = muestra.solicitud_ensayo.id
            except SolicitudEnsayo.DoesNotExist:
                pass

            muestras_list.append({
                'id': muestra.pk,
                'codigo_muestra': muestra.codigo_muestra,
                'descripcion_muestra': muestra.descripcion_muestra,
                'tipo_muestra': muestra.tipo_muestra,
                'fecha_recepcion': muestra.fecha_recepcion.strftime('%Y-%m-%d') if muestra.fecha_recepcion else 'N/A', 
                'estado': muestra.estado, 
                'estado_display': muestra.get_estado_display(), # Útil para la UI
                'solicitud_id': solicitud_id, 
            })
        
        proyecto = Proyecto.objects.get(id=proyecto_id)

        return JsonResponse({
            'status': 'success', 
            'muestras': muestras_list,
            'proyecto_estado': proyecto.estado
        })
        
    except Proyecto.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'El proyecto no existe.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error interno: {str(e)}'}, status=500)
 

def generar_o_redirigir_solicitud(request, muestra_id):
    """
    Verifica si la SolicitudEnsayo existe. Si no, la crea con su código.
    Siempre redirige al formulario de llenado (pagina_registro_solicitud).
    """
    muestra = get_object_or_404(Muestra, pk=muestra_id)
    
    try:
        solicitud_existente = SolicitudEnsayo.objects.get(muestra=muestra)
        
        # Si ya existe y la vista es llamada, el usuario verá el mensaje de Solicitud Existente
        # y un enlace para "Ver Solicitud" (o ir a la página de llenado/detalle)
        return redirect(reverse('pagina_registro_solicitud', kwargs={'solicitud_id': solicitud_existente.pk}))
        
    except SolicitudEnsayo.DoesNotExist:
        # Generación de código: Asegúrate de que esta lógica coincida con tus reglas de negocio
        nuevo_codigo = f"SOL-{muestra.proyecto.codigo_proyecto or 'TEMP'}-{muestra.codigo_muestra}"
        
        try:
            # Crea la solicitud mínima
            solicitud_existente = SolicitudEnsayo.objects.create(
                muestra=muestra,
                codigo_solicitud=nuevo_codigo,
                estado='BORRADOR', 
                generada_por=request.user.trabajadorprofile
            )
        except Exception as e:
            # Manejo de error si la creación falla
            return render(request, 'error_page.html', {'message': f'Error al crear Solicitud: {e}'}, status=500)

    # Redirigir a la vista de registro/llenado
    return redirect(reverse('pagina_registro_solicitud', kwargs={'solicitud_id': solicitud_existente.pk}))


# ---------------------------------------------------------------------------------
# 2. FUNCIÓN: LLENADO/REGISTRO (Paso 2)
#    Renderiza el formulario HTML.
# ---------------------------------------------------------------------------------

def pagina_registro_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudEnsayo, pk=solicitud_id)
    muestra = solicitud.muestra
    proyecto = muestra.proyecto
    
    solicitud_ya_detallada = DetalleEnsayo.objects.filter(solicitud=solicitud).exists() 

    tecnico_generador_id = None
    if solicitud.generada_por:
        tecnico_generador_id = solicitud.generada_por.id
    elif request.user.is_authenticated and hasattr(request.user, 'trabajadorprofile'):
        tecnico_generador_id = request.user.trabajadorprofile.id

    detalles_cotizacion_qs = CotizacionDetalle.objects.none()
    try:
        cotizacion = Cotizacion.objects.get(proyecto=proyecto) 
        detalles_cotizacion_qs = cotizacion.detalles_cotizacion.all().select_related('servicio')
    except Cotizacion.DoesNotExist:
        pass 
        
    tipos_ensayo_db = list(TipoEnsayo.objects.all().values('id', 'nombre', 'codigo_interno'))
    ROLES_LABORATORIO = ['TECNICO', 'JEFE_LAB', 'SUPERVISOR']
    tecnicos_db = list(TrabajadorProfile.objects.filter(role__in=ROLES_LABORATORIO).values('id', 'nombre_completo'))
    normas_db = list(Norma.objects.all().values('id', 'nombre', 'codigo'))
    metodos_db = list(Metodo.objects.all().values('id', 'nombre', 'codigo'))

    

    detalles_para_js = []
    for detalle in detalles_cotizacion_qs:
        tipo_ensayo_inicial_id = getattr(detalle, 'tipo_ensayo_id', None) 
        tecnico_inicial_id = getattr(detalle, 'tecnico_inicial_id', None) 
        
        detalles_para_js.append({
            'cotizacion_detalle_id': detalle.pk,
            'descripcion': getattr(detalle.servicio, 'nombre', ''), 
            'norma_precargada': getattr(detalle.servicio, 'norma_aplicable', ''),
            'metodo_precargado': getattr(detalle.servicio, 'metodo_aplicable', ''),
            'fecha_limite': (proyecto.fecha_entrega_estimada or timezone.now()).strftime('%Y-%m-%d'), 
            'observaciones_detalle': '', 
            'tipo_ensayo_id': tipo_ensayo_inicial_id, 
            'tecnico_inicial_id': tecnico_inicial_id, 
        })

    detalles_cotizacion_json = json.dumps(detalles_para_js)

    context = {
        'muestra': muestra,
        'solicitud': solicitud,
        'solicitud_ya_detallada': solicitud_ya_detallada,
        'tecnico_generador_id': tecnico_generador_id, 
        'tecnicos': tecnicos_db,
        'tipos_ensayo': tipos_ensayo_db,
        'normas': normas_db,
        'metodos': metodos_db, 
        'detalles_cotizacion_json': detalles_cotizacion_json, 
        'logged_user_id': request.user.trabajadorprofile.id if request.user.is_authenticated and hasattr(request.user, 'trabajadorprofile') else 0,
    }
    
    return render(request, 'proyectos/registro_solicitud.html', context)

# ---------------------------------------------------------------------------------
# 3. FUNCIÓN: GUARDADO/ACTUALIZACIÓN (Paso 3 - AJAX POST)
#    Crea/Actualiza SolicitudEnsayo, DetalleEnsayo y AsignacionTipoEnsayo.
# ---------------------------------------------------------------------------------

@csrf_exempt
def actualizar_solicitud_y_detalles(request, solicitud_id):
    """
    Procesa la solicitud POST para actualizar la cabecera y guardar los DetalleEnsayo 
    y AsignacionTipoEnsayo anidados.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)

    try:
        data = json.loads(request.body)
        solicitud = get_object_or_404(SolicitudEnsayo, pk=solicitud_id)
        
        with transaction.atomic():
            
            # 1. ACTUALIZAR CABECERA
            solicitud.generada_por_id = data.get('generada_por_id', solicitud.generada_por_id)
            solicitud.estado = 'PENDIENTE' 
            solicitud.save()

            # 2. ELIMINAR DETALLES Y ASIGNACIONES (para reescribir)
            # 💥 CORRECCIÓN DEL FieldError 💥
            DetalleEnsayo.objects.filter(solicitud=solicitud).delete()
            
            # 3. CREAR NUEVOS DETALLES Y ASIGNACIONES
            for detalle_data in data.get('detalles', []):
                
                # CREAR DetalleEnsayo
                detalle = DetalleEnsayo.objects.create(
                    solicitud=solicitud, # 💥 Usamos 'solicitud' 💥
                    descripcion=detalle_data.get('descripcion'),
                    norma_aplicable=detalle_data.get('norma'),
                    metodo_aplicable=detalle_data.get('metodo'),
                    fecha_limite=detalle_data.get('fecha_limite'),
                    observaciones_detalle=detalle_data.get('observaciones_detalle'), # Nuevo campo
                    cotizacion_detalle_id=detalle_data.get('cotizacion_detalle_id') or None, 
                )

                # CREAR AsignacionTipoEnsayo
                for asignacion in detalle_data.get('tipos_asignaciones', []):
                    AsignacionTipoEnsayo.objects.create(
                        detalle=detalle, # Usamos 'detalle' (nombre de la FK en AsignacionTipoEnsayo)
                        tipo_ensayo_id=asignacion['tipo_ensayo_id'],
                        tecnico_asignado_id=asignacion['tecnico_asignado_id']
                    )

        return JsonResponse({'codigo': solicitud.codigo_solicitud, 'solicitud_id': solicitud.pk}, status=200)

    except SolicitudEnsayo.DoesNotExist:
        return JsonResponse({'error': 'Solicitud de Ensayo no encontrada.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)