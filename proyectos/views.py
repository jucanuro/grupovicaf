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
# IMPORTACIONES CORREGIDAS
from .models import Proyecto, OrdenDeEnsayo, Muestra 
# Asumo que estos modelos están disponibles o los reemplaza por sus nombres correctos
from clientes.models import Cliente as Cliente # Asumo que Cliente es ClienteProfile
from servicios.models import Cotizacion
# Necesitas el modelo ResultadoEnsayo para una de tus funciones
try:
    from .models import ResultadoEnsayo 
except ImportError:
    # Placeholder si el modelo ResultadoEnsayo no está en .models (ajustar según su app)
    class ResultadoEnsayo:
        DoesNotExist = Exception 
        pass 
# ----------------------------------------------------------------------------------


@login_required
def lista_proyectos(request):
    """
    Muestra la lista de proyectos con búsqueda y paginación.
    Permite filtrar por proyectos pendientes de registro de muestras.
    """
    query = request.GET.get('q')
    estado_filtro = request.GET.get('estado')

    # Obtenemos todos los proyectos y los ordenamos por fecha
    proyectos_list = Proyecto.objects.all().order_by('-creado_en')
    
    if query:
        proyectos_list = proyectos_list.filter(
            Q(nombre_proyecto__icontains=query) |
            Q(cliente__razon_social__icontains=query)
        )
    
    if estado_filtro:
        proyectos_list = proyectos_list.filter(estado=estado_filtro)

    # Añadimos la información de la cotización a cada proyecto
    proyectos_con_cotizacion = []
    for proyecto in proyectos_list:
        # CORRECCIÓN: Usar el nombre del campo de relación (cotizacion_relacionada)
        cotizacion = proyecto.cotizacion_relacionada 
        if cotizacion:
            proyecto.monto_total = cotizacion.monto_total
            # CORRECCIÓN: Acceso a Voucher
            proyecto.numero_voucher = cotizacion.voucher.codigo if hasattr(cotizacion, 'voucher') and cotizacion.voucher else 'N/A'
        else:
            proyecto.monto_total = 'N/A'
            proyecto.numero_voucher = 'N/A'
        proyectos_con_cotizacion.append(proyecto)

    paginator = Paginator(proyectos_con_cotizacion, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'proyectos': page_obj,
        'query': query,
        # Asumo que ESTADO_PROYECTO es una tupla definida en Proyecto.
        'estados': Proyecto.ESTADO_PROYECTO,
        'estado_seleccionado': estado_filtro,
    }
    return render(request, 'proyectos/proyectos_list.html', context)


@login_required
def crear_proyecto(request):
    """
    Crea un nuevo proyecto.
    """
    # CORRECCIÓN: Usar Cliente (ClienteProfile)
    clientes = Cliente.objects.all() 
    cotizaciones = Cotizacion.objects.all()
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre_proyecto')
        cliente_id = request.POST.get('cliente')
        cotizacion_id = request.POST.get('cotizacion')
        
        # CORRECCIÓN: Usar Cliente (ClienteProfile)
        cliente = get_object_or_404(Cliente, pk=cliente_id) 
        cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_id) if cotizacion_id else None

        Proyecto.objects.create(
            nombre_proyecto=nombre,
            cliente=cliente,
            cotizacion_relacionada=cotizacion
        )
        return redirect('proyectos:lista_proyectos')

    context = {
        'clientes': clientes,
        'cotizaciones': cotizaciones
    }
    return render(request, 'proyectos/proyecos_form.html', context)


@login_required
def editar_proyecto(request, pk):
    """
    Edita un proyecto existente.
    """
    proyecto = get_object_or_404(Proyecto, pk=pk)
    # CORRECCIÓN: Usar Cliente (ClienteProfile)
    clientes = Cliente.objects.all()
    cotizaciones = Cotizacion.objects.all()
    
    if request.method == 'POST':
        proyecto.nombre_proyecto = request.POST.get('nombre_proyecto')
        # CORRECCIÓN: Usar Cliente (ClienteProfile)
        proyecto.cliente = get_object_or_404(Cliente, pk=request.POST.get('cliente')) 
        cotizacion_id = request.POST.get('cotizacion')
        proyecto.cotizacion_relacionada = get_object_or_404(Cotizacion, pk=cotizacion_id) if cotizacion_id else None
        
        proyecto.save()
        return redirect('proyectos:lista_proyectos')
    
    context = {
        'proyecto': proyecto,
        'clientes': clientes,
        'cotizaciones': cotizaciones
    }
    return render(request, 'proyectos/proyectos_form.html', context)


@login_required
def eliminar_proyecto(request, pk):
    """
    Elimina un proyecto.
    """
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if request.method == 'POST':
        proyecto.delete()
        return redirect('proyectos:lista_proyectos')
    
    context = {'proyecto': proyecto}
    return render(request, 'proyectos/eliminar_proyecto.html', context)


# ----------------------------------------------------------------------
# 🟢 FUNCIÓN FALTANTE 1: VISTA CENTRAL DE PROYECTO (Resuelve el error en urls.py)
# ----------------------------------------------------------------------
@login_required
def detalle_proyecto(request, pk): 
    """
    Vista de marcador de posición para detalle de proyecto. 
    Se añadió para resolver el AttributeError en urls.py. Si no la usa, es un placeholder.
    """
    proyecto = get_object_or_404(Proyecto, pk=pk)
    # Reemplace 'proyectos/placeholder_detalle.html' por su plantilla de detalle si existe.
    return render(request, 'proyectos/placeholder_detalle.html', {'proyecto': proyecto})


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


@csrf_exempt
# CORRECCIÓN: Cambié el nombre a 'crear_muestra' para que coincida con el JS y evitar duplicidad.
def crear_muestra(request): 
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            proyecto_id = data.get('proyecto_id')
            
            # --- Validaciones y Obtención del Proyecto ---
            if not proyecto_id:
                return JsonResponse({'status': 'error', 'message': 'El ID del proyecto no puede ser nulo.'}, status=400)

            try:
                proyecto = Proyecto.objects.get(id=proyecto_id)
            except Proyecto.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'El proyecto no existe.'}, status=404)

            # Evitar duplicidad: verificar si la muestra ya existe para este proyecto
            codigo_muestra = data.get('codigo_muestra')
            if Muestra.objects.filter(proyecto=proyecto, codigo_muestra=codigo_muestra).exists():
                return JsonResponse({'status': 'error', 'message': f'Ya existe una muestra con el código "{codigo_muestra}" para este proyecto.'}, status=400)

            # --- CORRECCIÓN DE FECHAS: Convertir string a fecha o None ---
            def get_date_or_none(date_string):
                return date_string if date_string else None
            
            with transaction.atomic():
                # --- Creación de Muestra ---
                muestra = Muestra.objects.create(
                    proyecto=proyecto,
                    codigo_muestra=codigo_muestra,
                    # Aquí asumo que tiene campos como descripcion_muestra y ensayos_a_realizar en su modelo
                    # Si el JS no los envía, deben ser opcionales en el modelo.
                    descripcion_muestra=data.get('descripcion_muestra', ''),
                    id_lab=data.get('id_lab'),
                    tipo_muestra=data.get('tipo_muestra'),
                    masa_aprox_kg=data.get('masa_aprox_kg'),
                    fecha_recepcion=get_date_or_none(data.get('fecha_recepcion')),
                    fecha_fabricacion=get_date_or_none(data.get('fecha_fabricacion')),
                    fecha_ensayo_rotura=get_date_or_none(data.get('fecha_ensayo_rotura')),
                    informe=data.get('informe'),
                    fecha_informe=get_date_or_none(data.get('fecha_informe')),
                    # Asumo que el estado inicial debe ser 'REGISTRADA' o similar
                    estado=data.get('estado', 'REGISTRADA'), 
                    ensayos_a_realizar=data.get('ensayos_a_realizar', '')
                )
                
                # --- Creación de Orden de Ensayo (vinculada a la Muestra) ---
                orden_ensayo = OrdenDeEnsayo.objects.create(
                    muestra=muestra,
                    proyecto=proyecto,
                    # Se usa el código de la muestra o se genera uno nuevo.
                    codigo_orden=f"OTE-{muestra.codigo_muestra}", 
                    tipo_ensayo="Ensayo de " + data.get('tipo_muestra', 'Muestra Genérica'),
                    fecha_entrega_programada=timezone.now().date(),
                    estado_orden='PENDIENTE'
                )

                # --- LÓGICA DE ACTUALIZACIÓN DEL PROYECTO ---
                # Esta lógica debe actualizar los contadores del proyecto.
                # CORRECCIÓN: No se necesita volver a filtrar, solo contar las existentes.
                proyecto.numero_muestras_registradas = Muestra.objects.filter(proyecto=proyecto).count() 
                
                if proyecto.estado == 'PENDIENTE':
                    proyecto.estado = 'EN_CURSO'
                
                proyecto.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Muestra y Orden de Ensayo creadas correctamente.',
                'muestra': {
                    'codigo_muestra': muestra.codigo_muestra,
                    'tipo_muestra': muestra.tipo_muestra,
                    'estado': muestra.estado,
                    'orden_ensayo_id': orden_ensayo.id 
                }
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Método de solicitud no permitido.'}, status=405)


@require_GET
def muestras_del_proyecto(request, proyecto_id):
    """
    Devuelve la lista de muestras para un proyecto específico en formato JSON.
    """
    try:
        # CORRECCIÓN: Uso de select_related para ForeignKey (proyecto) y prefetch_related para ManyToOne (ordenes)
        muestras = Muestra.objects.filter(proyecto_id=proyecto_id).order_by('-creado_en').prefetch_related('ordenes')
        
        muestras_list = [
            {
                'id': muestra.pk,
                'codigo_muestra': muestra.codigo_muestra,
                'descripcion_muestra': muestra.descripcion_muestra,
                # CORRECCIÓN: Manejo seguro de la fecha.
                'fecha_recepcion': muestra.fecha_recepcion.strftime('%Y-%m-%d') if muestra.fecha_recepcion else 'N/A', 
                'estado': muestra.estado, # Usamos el valor del campo
                # CORRECCIÓN: OrdenDeEnsayo es una relación de uno a muchos (ordenes) si no se definió como OneToOne.
                'orden_ensayo_id': muestra.ordenes.first().id if muestra.ordenes.exists() else None, 
            }
            for muestra in muestras
        ]
        
        proyecto = Proyecto.objects.get(id=proyecto_id)

        return JsonResponse({
            'status': 'success', 
            'muestras': muestras_list,
            'proyecto_estado': proyecto.estado
        })
        
    except Proyecto.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'El proyecto no existe.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    
@login_required
def orden_de_ensayo_form(request, orden_id):
    # 'orden_id' debe coincidir con lo que definiste en la URL
    orden = get_object_or_404(OrdenDeEnsayo, pk=orden_id)
    
    # ... tu lógica aquí ...
    return render(request, 'proyectos/orden_ensayo_form.html', {'orden': orden})
    
    
@login_required
def orden_de_ensayo_documento(request, pk):
    """
    Vista para visualizar el Documento/Ficha de la Orden de Ensayo.
    """
    orden = get_object_or_404(OrdenDeEnsayo, pk=pk)
    
    muestra = orden.muestra
    proyecto = orden.proyecto
    
    # **Acción Clave:** Si la orden está pendiente, la marcamos como 'EN_PROCESO'.
    if orden.estado_orden == 'PENDIENTE':
        orden.estado_orden = 'EN_PROCESO'
        orden.save()
        
    # El técnico necesita saber si ya existen resultados para esta muestra
    # CORRECCIÓN: Asumo que el modelo Muestra tiene un related_name='resultados' hacia ResultadoEnsayo
    try:
        resultado_actual = muestra.resultados.latest('creado_en') 
    except ResultadoEnsayo.DoesNotExist:
        resultado_actual = None 

    context = {
        'orden': orden,
        'muestra': muestra,
        'proyecto': proyecto,
        'resultado_actual': resultado_actual,
    }
    return render(request, 'proyectos/orden_ensayo_documento.html', context)


@login_required
def registro_resultado_form(request, muestra_pk):
    """
    Vista para el formulario de ingreso de datos para una Muestra específica.
    """
    muestra = get_object_or_404(Muestra, pk=muestra_pk)
    # CORRECCIÓN: Obtener la orden correctamente
    orden = muestra.ordenes.first() 
    
    if request.method == 'POST':
        # Aquí va la lógica de Formulario/Formset para crear o actualizar ResultadoEnsayo
        
        if orden:
            orden.estado_orden = 'RESULTADOS_REGISTRADOS'
            orden.save()
        
        # return redirect('alguna_vista_de_exito') 
        pass

    context = {
        'muestra': muestra,
        'orden': orden,
    }
    return render(request, 'proyectos/registro_resultado_form.html', context)


# ----------------------------------------------------------------------
# 🟢 FUNCIÓN FALTANTE 2: GENERAR ORDENES DE ENSAYO (Resuelve el error en urls.py)
# ----------------------------------------------------------------------
@login_required
@require_POST
def generar_ordenes_de_ensayo(request):
    """
    Recibe la solicitud POST (vía AJAX/JavaScript) para crear las Órdenes de Ensayo.
    """
    try:
        # Lógica de ejemplo: Buscamos muestras que están LISTAS P/ ENSAYO y sin orden
        muestras_listas = Muestra.objects.filter(
            estado='LISTO P/ ENSAYO', 
            ordenes__isnull=True # Asumo que el related_name es 'ordenes'
        )
        
        ordenes_creadas = 0
        with transaction.atomic():
            for muestra in muestras_listas:
                # 1. Creamos la Orden de Ensayo
                orden = OrdenDeEnsayo.objects.create(
                    codigo_orden=f"OTE-{muestra.codigo_muestra}",
                    muestra=muestra,
                    proyecto=muestra.proyecto,
                    fecha_creacion=timezone.now(),
                    estado_orden='PENDIENTE'
                )
                # 2. Actualizamos la Muestra
                # Muestra.ordenes ya se vincula automáticamente si OrdenDeEnsayo tiene ForeignKey a Muestra
                muestra.estado = 'ORDEN EMITIDA'
                muestra.save()
                ordenes_creadas += 1

        if ordenes_creadas > 0:
            return JsonResponse({
                'message': f'Órdenes de Ensayo creadas exitosamente para {ordenes_creadas} muestras.', 
                'error': False,
                'count': ordenes_creadas
            })
        else:
             return JsonResponse({'message': 'No se encontraron muestras que requieran una nueva orden.', 'error': False}, status=200)

    except Exception as e:
        return JsonResponse({'message': f'Error al generar órdenes: {str(e)}', 'error': True}, status=500)