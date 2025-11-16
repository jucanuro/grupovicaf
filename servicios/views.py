from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db import transaction 
from django.contrib.auth.decorators import login_required
from weasyprint import HTML
from django.forms.models import model_to_dict
from django.contrib import messages
from django.template.loader import get_template
from django.forms.models import model_to_dict # Útil para serializar objetos
from decimal import Decimal, InvalidOperation
import json
import logging

# Log para capturar errores internos
logger = logging.getLogger(__name__)

# Nota: Se asume que el modelo se llama 'Cliente' en lugar de 'ClienteProfile'
from proyectos.models import Proyecto
from .models import (
    Servicio, 
    Norma, 
    Metodo, 
    DetalleServicio, 
    Cotizacion, 
    CotizacionDetalle, 
    Voucher, 
    Cliente,
    CategoriaServicio
)

# ---------------------------------------------------------------
# Vistas para la gestión de Servicios (CRUD y API)
# ---------------------------------------------------------------

@login_required
def lista_servicios(request):
    """ Muestra una lista de todos los servicios con paginación y búsqueda. """
    query = request.GET.get('q')
    
    # Uso de prefetch_related para cargar Normas y Métodos de manera eficiente
    servicios_list = Servicio.objects.all().prefetch_related('normas', 'metodos').order_by('nombre')
    
    if query:
        servicios_list = servicios_list.filter(
            Q(nombre__icontains=query) | 
            Q(descripcion__icontains=query) |
            Q(codigo_facturacion__icontains=query)
        )

    paginator = Paginator(servicios_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    categorias_disponibles = CategoriaServicio.objects.all().order_by('nombre')


    context = {
        'servicios': page_obj,
        'query': query,
        'categorias_disponibles': categorias_disponibles,

    }
    return render(request, 'servicios/servicios_list.html', context)

def obtener_detalle_servicio_api(request, pk):
    """
    Devuelve los detalles de un servicio en formato JSON para uso en el modal.
    """
    servicio = get_object_or_404(Servicio, pk=pk)
    detalle = getattr(servicio, 'detalleservicio', None)
    
    data = {
        'nombre': servicio.nombre,
        'descripcion': servicio.descripcion,
        'imagen_url': servicio.imagen.url if servicio.imagen else None,
        'normas': [norma.nombre for norma in servicio.normas.all()],
        'metodos': [metodo.nombre for metodo in servicio.metodos.all()],
        'detalle': {
            'titulo': detalle.titulo,
            'descripcion': detalle.descripcion,
            'imagen_url': detalle.imagen.url if detalle.imagen else None,
        } if detalle else None
    }
    return JsonResponse(data)

logger = logging.getLogger(__name__)
def _procesar_guardado_servicio(request, servicio=None):
    """Función auxiliar para manejar la lógica de guardado y actualización (DRY)."""
    try:
        with transaction.atomic():
            precio_base_str = request.POST.get('precio_base', '0').replace(',', '.')
            
            try:
                precio_base = Decimal(precio_base_str)
            except Exception:
                raise ValueError("El campo 'Precio Base' debe ser un número válido.")
            
            # --- CORRECCIÓN 1: Usar el nombre de relación correcto ('detalle_web') ---
            detalle_servicio = None
            if servicio:
                try:
                    detalle_servicio = servicio.detalle_web 
                except DetalleServicio.DoesNotExist:
                    pass

            precio_urgente_str = request.POST.get('precio_urgente', '').replace(',', '.')
            precio_urgente = Decimal(precio_urgente_str) if precio_urgente_str else None

            categoria_id = request.POST.get('categoria')
            imagen_file = request.FILES.get('imagen')
            
            # --- CORRECCIÓN 2: Obtener el objeto CategoriaServicio ---
            categoria_obj = None
            if categoria_id:
                try:
                    categoria_obj = CategoriaServicio.objects.get(pk=categoria_id)
                except CategoriaServicio.DoesNotExist:
                    raise ValueError("La categoría seleccionada no es válida.")

            data_servicio = {
                'nombre': request.POST.get('nombre'),
                'descripcion': request.POST.get('descripcion'),
                'codigo_facturacion': request.POST.get('codigo_facturacion'),
                'precio_base': precio_base,
                'unidad_base': request.POST.get('unidad_base'),
                'esta_acreditado': request.POST.get('esta_acreditado') == 'on',
                'categoria': categoria_obj, # <-- ¡Asignación del objeto Categoría!
            }
            
            if not data_servicio['nombre'] or not data_servicio['descripcion']:
                raise ValueError("El nombre y la descripción son obligatorios.")

            if servicio:
                for key, value in data_servicio.items():
                    setattr(servicio, key, value)
                
                if imagen_file:
                    servicio.imagen = imagen_file
                
                servicio.save()
            else:
                servicio = Servicio.objects.create(**data_servicio, imagen=imagen_file)

            normas_ids = request.POST.getlist('normas')
            metodos_ids = request.POST.getlist('metodos')
            
            servicio.normas.set(normas_ids)
            servicio.metodos.set(metodos_ids)
            
            detalle_imagen_file = request.FILES.get('detalle_imagen')
            
            detalle_data = {
                'titulo': request.POST.get('detalle_titulo'),
                'descripcion': request.POST.get('detalle_descripcion'),
            }
            
            if detalle_data['titulo'] or detalle_data['descripcion'] or detalle_imagen_file:
                defaults = detalle_data.copy()
                if detalle_imagen_file:
                    defaults['imagen'] = detalle_imagen_file
                elif detalle_servicio and not detalle_imagen_file and detalle_servicio.imagen:
                    defaults['imagen'] = detalle_servicio.imagen
                
                DetalleServicio.objects.update_or_create(
                    servicio=servicio,
                    defaults=defaults
                )

        return None 
    
    except ValueError as e:
        return f'Error de validación de datos: {e}'
    except Exception as e:
        # logger.error(f"Error crítico al guardar servicio: {e}") # Descomenta si usas logging
        return f'Ocurrió un error inesperado al guardar el servicio: {e}'

@login_required
def crear_editar_servicio(request, pk=None):
    """Maneja la lógica de Creación (pk=None) y Edición (pk existe)."""
    servicio = None
    error = None
    
    if pk:
        servicio = get_object_or_404(Servicio, pk=pk)
        # --- CORRECCIÓN 1: Se elimina el bloque try/except que fallaba. ---
        # El acceso seguro se hace en el contexto final con 'getattr'.

    if request.method == 'POST':
        error = _procesar_guardado_servicio(request, servicio)
        if not error:
            return redirect('servicios:lista_servicios')
        
        if servicio and pk:
            servicio.refresh_from_db()

    categorias_disponibles = CategoriaServicio.objects.all().order_by('nombre')
    normas_disponibles = Norma.objects.all()
    metodos_disponibles = Metodo.objects.all()
    
    context = {
        'servicio': servicio,
        # Acceso seguro a detalle_servicio usando 'detalle_web'
        'detalle_servicio': getattr(servicio, 'detalle_web', None) if servicio else None, 
        'categorias_disponibles': categorias_disponibles,
        'normas_disponibles': normas_disponibles,
        'metodos_disponibles': metodos_disponibles,
        'error': error,
    }
    return render(request, 'servicios/servicios_form.html', context)

@login_required
def eliminar_servicio(request, pk):
    """Maneja la eliminación de un servicio."""
    servicio = get_object_or_404(Servicio, pk=pk)
    error = None
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                servicio.delete()
            return redirect('servicios:lista_servicios')
        except Exception as e:
            logger.error(f"Error al eliminar servicio {pk}: {e}")
            error = f'No se pudo eliminar el servicio. Puede que existan dependencias protegidas: {e}'
    
    return render(request, 'servicios/servicio_confirm_delete.html', {
        'servicio': servicio,
        'error': error
    })

def obtener_datos_servicio_json(request, pk):
    """
    Retorna los datos detallados de un Servicio específico en formato JSON, 
    preparado para ser consumido por un modal de visualización en JavaScript.
    """
    servicio = get_object_or_404(
        Servicio.objects.select_related('categoria'), 
        pk=pk
    )

    detalle_data = None
    try:
        detalle_web = servicio.detalle_web 
        detalle_data = {
            'titulo': getattr(detalle_web, 'titulo', 'Sin título'),
            'descripcion': getattr(detalle_web, 'descripcion', 'Sin descripción de detalle.'),
            'imagen_url': request.build_absolute_uri(detalle_web.imagen.url) if detalle_web.imagen else None,
        }
    except DetalleServicio.DoesNotExist:
        pass
    except Exception:
        pass

    normas_codigos = [norma.codigo for norma in servicio.normas.all()]
    metodos_codigos = [metodo.codigo for metodo in servicio.metodos.all()]


    data = {
        'nombre': servicio.nombre,
        'descripcion': servicio.descripcion,
        'codigo_facturacion': servicio.codigo_facturacion,
        'unidad_base': servicio.unidad_base,
        'esta_acreditado': servicio.esta_acreditado,
        'categoria': servicio.categoria.nombre if servicio.categoria else 'Sin Categoría', 
        'precio_base': str(servicio.precio_base) if servicio.precio_base else '0.00', 
        'imagen_url': request.build_absolute_uri(servicio.imagen.url) if servicio.imagen else None,
        'normas': normas_codigos,
        'metodos': metodos_codigos,
        'detalle': detalle_data, 
    }
    
    return JsonResponse(data)

@login_required
def lista_cotizaciones(request):
    """ Lista las cotizaciones, filtradas por usuario no staff o todas para staff. """
    query = request.GET.get('q')
    
    # Uso de select_related para cargar el cliente de forma eficiente
    cotizaciones_list = Cotizacion.objects.select_related('cliente').order_by('-fecha_creacion')
    
    # 🎯 Lógica de filtrado por cliente (adaptar a tu relación de usuario-cliente real)
    if not request.user.is_superuser:
        try:
            # Asumiendo que el User tiene una relación O2O o FK con Cliente
            cliente_asociado = Cliente.objects.get(usuario=request.user) 
            cotizaciones_list = cotizaciones_list.filter(cliente=cliente_asociado)
        except Cliente.DoesNotExist:
            cotizaciones_list = Cotizacion.objects.none()

    if query:
        cotizaciones_list = cotizaciones_list.filter(
            Q(numero_oferta__icontains=query) | 
            Q(cliente__razon_social__icontains=query) |
            Q(estado__icontains=query)
        )

    paginator = Paginator(cotizaciones_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'cotizaciones': page_obj,
        'query': query,
    }
    return render(request, 'servicios/cotizacion_list.html', context)

@login_required
def detalle_cotizacion(request, pk):
    """ Muestra los detalles de una cotización específica. """
    # Uso de select_related y prefetch_related para cargar todos los datos de una vez
    cotizacion = get_object_or_404(
        Cotizacion.objects.select_related('cliente', 'trabajador_responsable')
                          .prefetch_related('detalles_cotizacion', 
                                            'detalles_cotizacion__servicio',
                                            'detalles_cotizacion__norma',
                                            'detalles_cotizacion__metodo'), 
        pk=pk
    )
    
    # Obtener el Voucher si existe para auditoría
    voucher = Voucher.objects.filter(cotizacion=cotizacion).first()

    context = {
        'cotizacion': cotizacion,
        'detalles': cotizacion.detalles_cotizacion.all(),
        'voucher': voucher,
    }
    return render(request, 'servicios/cotizacion_detail.html', context)

@login_required
def crear_editar_cotizacion(request, pk=None):
    cotizacion = get_object_or_404(Cotizacion, pk=pk) if pk else None
    error = None

    if request.method == 'POST':
        try:
            with transaction.atomic():
                cliente = get_object_or_404(Cliente, pk=request.POST.get('cliente'))
                detalles_data = json.loads(request.POST.get('detalles_json'))
                
                if not detalles_data:
                    raise ValueError("La cotización debe tener al menos un servicio.")

                is_new = cotizacion is None 
                
                if is_new:
                    cotizacion = Cotizacion(cliente=cliente)
                
                fecha_generacion_str = request.POST.get('fecha_generacion')
                if fecha_generacion_str:
                    try:
                        cotizacion.fecha_generacion = date.fromisoformat(fecha_generacion_str)
                    except ValueError:
                        pass
                
                cotizacion.cliente = cliente
                cotizacion.asunto_servicio = request.POST.get('asunto_servicio')
                cotizacion.persona_contacto = request.POST.get('persona_contacto')
                cotizacion.correo_contacto = request.POST.get('correo_contacto')
                cotizacion.telefono_contacto = request.POST.get('telefono_contacto')

                servicio_general_pk = request.POST.get('servicio_general')
                if servicio_general_pk:
                    servicio_general_obj = get_object_or_404(CategoriaServicio, pk=servicio_general_pk)
                    cotizacion.servicio_general = servicio_general_obj
                else:
                    cotizacion.servicio_general = None
                
                cotizacion.plazo_entrega_dias = int(request.POST.get('plazo_entrega_dias') or 0)
                cotizacion.validez_oferta_dias = int(request.POST.get('validez_oferta_dias') or 0)
                cotizacion.forma_pago = request.POST.get('forma_pago')
                cotizacion.observaciones_condiciones = request.POST.get('observaciones_condiciones')
                
                tasa_igv_str = str(request.POST.get('tasa_igv', '0')).strip().replace(',', '.')
                cotizacion.tasa_igv = Decimal(tasa_igv_str) if tasa_igv_str else Decimal('0.00')

                cotizacion.save() 
                
                if not is_new:
                    cotizacion.detalles_cotizacion.all().delete()
                
                detalle_objs = []
                for item in detalles_data:
                    servicio_id_str = str(item.get('servicio_id')).strip()
                    if not servicio_id_str or not servicio_id_str.isdigit():
                        raise ValueError(f"ID de Servicio requerido no válido. Valor recibido: '{servicio_id_str}'.")

                    servicio_id = int(servicio_id_str)
                    servicio = Servicio.objects.get(pk=servicio_id) 
                    
                    norma_id_str = str(item.get('norma_id', '')).strip()
                    norma = None
                    if norma_id_str and norma_id_str.isdigit():
                        norma = Norma.objects.get(pk=int(norma_id_str))
                    
                    metodo_id_str = str(item.get('metodo_id', '')).strip()
                    metodo = None
                    if metodo_id_str and metodo_id_str.isdigit():
                        metodo = Metodo.objects.get(pk=int(metodo_id_str))
                    
                    cantidad_str = str(item.get('cantidad', '0')).strip().replace(',', '.')
                    precio_unitario_str = str(item.get('precio_unitario', '0')).strip().replace(',', '.')
                    
                    cantidad = Decimal(cantidad_str) if cantidad_str else Decimal('0.00') 
                    precio_unitario = Decimal(precio_unitario_str) if precio_unitario_str else Decimal('0.00')

                    total_detalle_calculado = cantidad * precio_unitario 
                    
                    detalle_objs.append(CotizacionDetalle(
                        cotizacion=cotizacion,
                        servicio=servicio,
                        norma=norma,
                        metodo=metodo,
                        descripcion_especifica=item.get('descripcion_especifica', servicio.descripcion),
                        unidad_medida=item.get('unidad_medida', servicio.unidad_base),
                        cantidad=cantidad,
                        precio_unitario=precio_unitario,
                        total_detalle=total_detalle_calculado, 
                    ))

                CotizacionDetalle.objects.bulk_create(detalle_objs)
                cotizacion.save()

                accion = "creada" if is_new else "actualizada"
                messages.success(request, f"¡Cotización {cotizacion.numero_oferta} {accion} con éxito! ✅")
                
                return redirect('servicios:lista_cotizaciones')

        except (ValueError, InvalidOperation, Cotizacion.DoesNotExist, Cliente.DoesNotExist, Servicio.DoesNotExist, CategoriaServicio.DoesNotExist) as e:
            error = f'Error de Guardado: Error en los datos de entrada o cálculo: {e}'
        except Exception as e:
            error = f'Ocurrió un error inesperado al procesar la cotización: {e}'
            
    clientes = Cliente.objects.all()
    servicios = Servicio.objects.all().prefetch_related('normas', 'metodos')
    
    servicio_grupos = CategoriaServicio.objects.all()
    
    servicios_con_detalles_json = json.dumps([
        {
            'pk': s.pk, 
            'nombre': s.nombre, 
            'unidad_base': s.unidad_base, 
            'precio_base': str(s.precio_base),
            'categoria_id': s.categoria_id, 
            'normas': [model_to_dict(n, fields=['pk', 'codigo', 'nombre']) for n in s.normas.all()],
            'metodos': [model_to_dict(m, fields=['pk', 'codigo', 'nombre']) for m in s.metodos.all()]
        } for s in servicios
    ])

    detalles_cotizacion_json = '[]'
    if cotizacion:
        detalles_cotizacion_json = json.dumps([
             {
                 'servicio_id': detalle.servicio.pk, 'descripcion_especifica': detalle.descripcion_especifica,
                 'norma_id': detalle.norma.pk if detalle.norma else None, 'metodo_id': detalle.metodo.pk if detalle.metodo else None,
                 'unidad_medida': detalle.unidad_medida, 'cantidad': str(detalle.cantidad), 'precio_unitario': str(detalle.precio_unitario),
             } for detalle in cotizacion.detalles_cotizacion.all()
         ])
    
    context = {
        'cotizacion': cotizacion,
        'clientes': clientes,
        'servicios': servicios,
        'servicios_con_detalles_json': servicios_con_detalles_json,
        'detalles_cotizacion_json': detalles_cotizacion_json,
        'error': error,
        'servicio_grupos': servicio_grupos, 
    }
    return render(request, 'servicios/cotizaciones_form.html', context)

crear_cotizacion = crear_editar_cotizacion
editar_cotizacion = crear_editar_cotizacion

@login_required
def eliminar_cotizacion(request, pk):
    """ Permite eliminar una cotización. """
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    if request.method == 'POST':
        if cotizacion.estado in ['Aceptada', 'En Progreso', 'Cerrada']:
            return render(request, 'servicios/cotizacion_confirm_delete.html', {
                'cotizacion': cotizacion,
                'error': 'No se puede eliminar una cotización que ya ha sido Aceptada o iniciada.'
            })
            
        try:
            with transaction.atomic():
                cotizacion.delete()
            return redirect('servicios:lista_cotizaciones')
        except Exception as e:
            logger.error(f"Error al eliminar cotización {pk}: {e}")
            return render(request, 'servicios/cotizacion_confirm_delete.html', {
                'cotizacion': cotizacion,
                'error': f'No se pudo eliminar la cotización: {e}'
            })

    return render(request, 'servicios/cotizacion_confirm_delete.html', {'cotizacion': cotizacion})

def generar_pdf_cotizacion(request, pk):
    """
    Muestra el HTML de la cotización directamente en el navegador
    para propósitos de depuración.
    """
    
    # 1. Preparar el QuerySet (Mantenemos la optimización)
    # Corregido: 'trabajador_responsable' es el campo correcto.
    cotizacion_qs = Cotizacion.objects.select_related(
        'cliente',                       
        'trabajador_responsable',        
    ).prefetch_related(
        'detalles_cotizacion', 
        'detalles_cotizacion__servicio',
        'detalles_cotizacion__norma', 
        'detalles_cotizacion__metodo', 
    )
    
    # 2. Obtener el objeto de la cotización
    cotizacion = get_object_or_404(cotizacion_qs, pk=pk)
    
    # 3. Preparar el contexto
    context = {'cotizacion': cotizacion}
    
    # 4. RENDERIZAR DIRECTAMENTE EL TEMPLATE HTML
    # Esto usa el motor de plantillas de Django para devolver el HTML plano.
    return render(request, 'servicios/cotizacion_pdf.html', context)

logger = logging.getLogger(__name__) 

@login_required
def aprobar_cotizacion(request, pk):
    """
    Aprueba una cotización, registra el voucher y crea el proyecto asociado, 
    todo dentro de una transacción.
    """
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    if cotizacion.estado != 'Pendiente':
        return render(request, 'servicios/aprobar_cotizacion.html', {
            'cotizacion': cotizacion, 
            'error': f"Esta cotización ya tiene estado: {cotizacion.estado}. No se puede aprobar."
        })

    if request.method == 'POST':
        # 1. Obtener datos
        codigo_voucher = request.POST.get('codigo_voucher')
        monto_pagado_str = request.POST.get('monto_pagado')
        imagen_voucher = request.FILES.get('imagen_voucher')
        
        # 2. Convertir monto (si falla, asume 0.00, no falla)
        try:
            monto_pagado = Decimal(monto_pagado_str)
        except (TypeError, InvalidOperation):
            monto_pagado = Decimal('0.00')

        # 3. Validar solo los campos que deseas que sean obligatorios (Código y Archivo)
        if not codigo_voucher:
            return render(request, 'servicios/aprobar_cotizacion.html', {
                'cotizacion': cotizacion,
                'error': 'El código de operación es requerido.'
            })
            
        if not imagen_voucher:
            return render(request, 'servicios/aprobar_cotizacion.html', {
                'cotizacion': cotizacion,
                'error': 'La imagen del voucher es requerida.'
            })

        # ********** LÓGICA DE VALIDACIÓN CORREGIDA **********
        # Eliminamos la condición `monto_pagado <= 0` de la validación crítica.
        # ****************************************************

        # ----------------------------------------------------
        # 1. Transacción Atómica para garantizar la integridad
        # ----------------------------------------------------
        try:
            with transaction.atomic():
                # A. Crear el registro del voucher
                voucher = Voucher.objects.create(
                    cotizacion=cotizacion,
                    codigo=codigo_voucher,
                    monto_pagado=monto_pagado, # Se registra el monto, aunque sea 0
                    imagen=imagen_voucher
                )
                
                # B. Actualizar el estado de la cotización
                cotizacion.estado = 'Aceptada'
                cotizacion.aprobada_por_cliente = True 
                cotizacion.save()

                # C. Preparar datos para el Proyecto
                nombre_proyecto = f"Proyecto - {cotizacion.asunto_servicio} ({cotizacion.numero_oferta})"
                codigo_proyecto = f"P-{cotizacion.numero_oferta}" 
                
                total_muestras = cotizacion.detalles_cotizacion.aggregate(Sum('cantidad'))['cantidad__sum'] or 0

                # D. Crear el nuevo proyecto
                nuevo_proyecto = Proyecto.objects.create(
                    cotizacion=cotizacion,
                    nombre_proyecto=nombre_proyecto,
                    codigo_proyecto=codigo_proyecto, 
                    cliente=cotizacion.cliente,
                    estado='PENDIENTE',
                    descripcion_proyecto="Proyecto generado automáticamente a partir de una cotización aceptada.",
                    monto_cotizacion=cotizacion.monto_total,
                    codigo_voucher=voucher.codigo,
                    numero_muestras=total_muestras,
                )
                
                return redirect('proyectos:lista_proyectos_pendientes')
        
        except Exception as e:
            logger.error(f"Error en la aprobación de cotización {pk} y creación de proyecto: {e}")
            return render(request, 'servicios/aprobar_cotizacion.html', {
                'cotizacion': cotizacion,
                'error': f'Error crítico en el proceso de aprobación: {e}'
            })
    
    # GET request
    context = {
        'cotizacion': cotizacion
    }
    return render(request, 'servicios/aprobar_cotizacion.html', context)

def buscar_servicios_api(request):
    """
    API para la búsqueda de servicios que devuelve una respuesta JSON (autocompletado).
    """
    query = request.GET.get('q', '')
    servicios = []
    if query:
        servicios_qs = Servicio.objects.filter(
            Q(nombre__icontains=query) | Q(codigo_facturacion__icontains=query)
        ).order_by('nombre')
        
        for servicio in servicios_qs:
            servicios.append({
                'pk': servicio.pk,
                'nombre': servicio.nombre,
                'codigo_facturacion': servicio.codigo_facturacion,
                'unidad_base': servicio.unidad_base,
                'precio_base': str(servicio.precio_base),
            })
    return JsonResponse(servicios, safe=False)


def buscar_cotizaciones_api(request):
    """ Endpoint API para la búsqueda dinámica de cotizaciones. """
    
    query = request.GET.get('q', '')
    data = []

    if query:
        # Búsqueda optimizada por número de oferta, cliente o asunto
        cotizaciones = Cotizacion.objects.filter(
            Q(numero_oferta__icontains=query) |
            Q(cliente__razon_social__icontains=query) |
            Q(asunto_servicio__icontains=query)
        ).select_related('cliente') # Clave para traer la relación del cliente

        for cotizacion in cotizaciones:
            monto_total = cotizacion.monto_total if cotizacion.monto_total is not None else Decimal('0.00')
            
            data.append({
                'pk': cotizacion.pk,
                'numero_oferta': cotizacion.numero_oferta,
                
                # ✅ CLAVE: Incluir el monto como string para JSON
                'monto_total': str(cotizacion.monto_total),
                
                # ✅ CLAVE: Incluir la razón social del cliente
                'cliente_razon_social': cotizacion.cliente.razon_social,
                
                'estado': cotizacion.estado,
                'estado_display': cotizacion.get_estado_display(), # Necesario si quieres la descripción
            })

    # Devuelve la lista de diccionarios como respuesta JSON
    return JsonResponse(data, safe=False)