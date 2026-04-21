import os
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.template.loader import get_template
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db import transaction 
from datetime import date
from django.db.models import Max
from django.contrib.auth.decorators import login_required
from weasyprint import HTML
from django.forms.models import model_to_dict
from django.contrib import messages
from django.template.loader import get_template
from django.forms.models import model_to_dict 
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import logging
from django.conf import settings
from xhtml2pdf import pisa
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph

logger = logging.getLogger(__name__)

from proyectos.models import Proyecto
from trabajadores.models import TrabajadorProfile
from clientes.models import Cliente
from .models import (
    Servicio,
    Norma,
    Metodo,
    Cotizacion,
    CotizacionDetalle,
    Voucher,
    CategoriaServicio,
    Subcategoria,
    CotizacionGrupo,
    PlantillaCotizacion,
    PlantillaGrupo,
    PlantillaDetalle,
    CatalogoCondicionSeccion,
    CatalogoCondicionItem,
    CotizacionCondicionSeccion,
    CotizacionCondicionItem,
    PlantillaCondicionSeccion,
    PlantillaCondicionItem,
)

@login_required
def lista_servicios(request):
    """ Muestra una lista de todos los servicios maestros con paginación y búsqueda. """
    query = request.GET.get('q')
    
    servicios_list = Servicio.objects.all().select_related('norma', 'metodo').order_by('nombre')
    
    if query:
        servicios_list = servicios_list.filter(
            Q(nombre__icontains=query) | 
            Q(codigo_facturacion__icontains=query)
        )

    paginator = Paginator(servicios_list, 7) 
    
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categorias_disponibles = CategoriaServicio.objects.all().order_by('nombre')

    context = {
        'servicios': page_obj, 
        'query': query,
        'categorias_disponibles': categorias_disponibles,
    }
    
    return render(request, 'servicios/servicios_list.html', context)

@login_required
def obtener_detalle_servicio_api(request, pk):
    """
    Devuelve los detalles técnicos del servicio. 
    Nota: Ya no devuelve categoría/subcategoría fija porque el modelo es independiente.
    """
    servicio = get_object_or_404(Servicio, pk=pk)
    
    data = {
        'nombre': servicio.nombre,
        'codigo_facturacion': servicio.codigo_facturacion,
        'precio_base': f"S/ {servicio.precio_base}",
        'norma': servicio.norma.codigo if servicio.norma else "No especifica",
        'metodo': servicio.metodo.nombre if servicio.metodo else "No especifica",
        'unidad_base': servicio.unidad_base,
        'esta_acreditado': servicio.esta_acreditado,
    }
    return JsonResponse(data)

def _procesar_guardado_servicio(request, servicio=None):
    """Lógica de guardado simplificada para el Servicio independiente."""
    try:
        with transaction.atomic():
            precio_base_str = request.POST.get('precio_base', '0').strip().replace(',', '.')
            try:
                precio_base = Decimal(precio_base_str)
                if precio_base < 0:
                    raise ValueError("El precio no puede ser negativo.")
                if precio_base > 999999.99:
                    raise ValueError("El precio no puede exceder 999,999.99")
            except (InvalidOperation, ValueError) as e:
                raise ValueError(f"El campo 'Precio Base' debe ser un número válido: {str(e)}")

            nombre = request.POST.get('nombre', '').strip()
            codigo_facturacion = request.POST.get('codigo_facturacion', '').strip()
            unidad_base = request.POST.get('unidad_base', 'Ensayo').strip()

            if not nombre or len(nombre) < 2 or len(nombre) > 200:
                raise ValueError("El nombre debe tener entre 2 y 200 caracteres.")
            
            if not codigo_facturacion or len(codigo_facturacion) < 2 or len(codigo_facturacion) > 50:
                raise ValueError("El código de facturación debe tener entre 2 y 50 caracteres.")
            
            import re
            if re.search(r'[<>]', nombre) or re.search(r'[<>]', codigo_facturacion):
                raise ValueError("Los campos no pueden contener caracteres especiales (< >).")

            data_servicio = {
                'nombre': nombre,
                'codigo_facturacion': codigo_facturacion,
                'precio_base': precio_base,
                'unidad_base': unidad_base[:50], 
                'esta_acreditado': request.POST.get('esta_acreditado') == 'on',
                'norma_id': request.POST.get('norma') or None,
                'metodo_id': request.POST.get('metodo') or None,
            }

            if servicio:
                for key, value in data_servicio.items():
                    setattr(servicio, key, value)
                servicio.save()
            else:
                servicio = Servicio.objects.create(**data_servicio)

        return None 
    
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Error al guardar servicio: {e}")
        return f'Error inesperado: {e}'

@login_required
def crear_editar_servicio(request, pk=None):
    servicio = None
    error = None
    
    if pk:
        servicio = get_object_or_404(Servicio, pk=pk)

    if request.method == 'POST':
        error = _procesar_guardado_servicio(request, servicio)
        if not error:
            return redirect('servicios:lista_servicios')

    context = {
        'servicio': servicio,
        'normas_disponibles': Norma.objects.all(),
        'metodos_disponibles': Metodo.objects.all(),
        'error': error,
    }
    return render(request, 'servicios/servicios_form.html', context)

@login_required
def eliminar_servicio(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    if request.method == 'POST':
        try:
            servicio.delete()
            return redirect('servicios:lista_servicios')
        except Exception as e:
            logger.error(f"Error al eliminar servicio {pk}: {e}")
    
    return render(request, 'servicios/servicio_confirm_delete.html', {'servicio': servicio})

   
from django.http import JsonResponse
from .models import Norma, Metodo

@login_required
@login_required
def crear_norma_ajax(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'})
    
    try:
        codigo = request.POST.get('codigo_norma', '').strip()
        nombre = request.POST.get('nombre_norma', '').strip()
        descripcion = request.POST.get('descripcion_norma', '').strip()

       
        if not codigo or len(codigo) < 1 or len(codigo) > 20:
            return JsonResponse({'success': False, 'error': 'Código debe tener entre 1 y 20 caracteres.'})
        
        if not nombre or len(nombre) < 1 or len(nombre) > 100:
            return JsonResponse({'success': False, 'error': 'Nombre debe tener entre 2 y 100 caracteres.'})
        
        if len(descripcion) > 500:
            return JsonResponse({'success': False, 'error': 'Descripción no puede exceder 500 caracteres.'})
        
        import re
        if re.search(r'[<>]', codigo) or re.search(r'[<>]', nombre) or re.search(r'[<>]', descripcion):
            logger.warning(f"Intento de XSS en crear_norma_ajax por usuario {request.user.username}")
            return JsonResponse({'success': False, 'error': 'Caracteres no permitidos detectados.'})

        if Norma.objects.filter(codigo=codigo).exists():
            return JsonResponse({'success': False, 'error': 'Ya existe una norma con este código.'})

        norma = Norma.objects.create(
            codigo=codigo,
            nombre=nombre,
            descripcion=descripcion
        )
        
        logger.info(f"Norma creada: {codigo} por usuario {request.user.username}")
        return JsonResponse({
            'success': True,
            'id': norma.id,
            'codigo': norma.codigo
        })
        
    except Exception as e:
        logger.error(f"Error en crear_norma_ajax: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Error interno del servidor.'})

@login_required
@login_required
def crear_metodo_ajax(request):
    if request.method == 'POST':
        try:
            codigo = request.POST.get('codigo_metodo', '').strip()
            nombre = request.POST.get('nombre_metodo', '').strip()
            descripcion = request.POST.get('descripcion_metodo', '').strip()

            if not codigo or len(codigo) < 1 or len(codigo) > 20:
                return JsonResponse({'success': False, 'error': 'Código debe tener entre 1 y 20 caracteres.'})
            
            if not nombre or len(nombre) < 1 or len(nombre) > 100:
                return JsonResponse({'success': False, 'error': 'Nombre debe tener entre 2 y 100 caracteres.'})
            
            if len(descripcion) > 500:
                return JsonResponse({'success': False, 'error': 'Descripción no puede exceder 500 caracteres.'})
            
            import re
            if re.search(r'[<>]', codigo) or re.search(r'[<>]', nombre) or re.search(r'[<>]', descripcion):
                logger.warning(f"Intento de XSS en crear_metodo_ajax por usuario {request.user.username}")
                return JsonResponse({'success': False, 'error': 'Caracteres no permitidos detectados.'})

            if Metodo.objects.filter(codigo=codigo).exists():
                return JsonResponse({'success': False, 'error': 'Ya existe un método con este código.'})

            metodo = Metodo.objects.create(
                codigo=codigo,
                nombre=nombre,
                descripcion=descripcion
            )
            
            logger.info(f"Método creado exitosamente: {codigo} por usuario {request.user.username}")
            
            return JsonResponse({
                'success': True,
                'id': metodo.id,
                'nombre': metodo.nombre,
                'codigo': metodo.codigo
            })
        except Exception as e:
            logger.error(f"Error al crear método por usuario {request.user.username}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Error interno del servidor.'})
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})
    
class NormaListView(ListView):
    model = Norma
    template_name = 'servicios/norma_list.html'
    context_object_name = 'normas'

class NormaCreateView(SuccessMessageMixin, CreateView):
    model = Norma
    fields = ['codigo', 'nombre', 'descripcion']
    template_name = 'servicios/norma_form.html'
    success_url = reverse_lazy('servicios:norma_list')
    success_message = "La norma técnica fue creada con éxito."

class NormaUpdateView(SuccessMessageMixin, UpdateView):
    model = Norma
    fields = ['codigo', 'nombre', 'descripcion']
    template_name = 'servicios/norma_form.html'
    success_url = reverse_lazy('servicios:norma_list')
    success_message = "La norma técnica fue actualizada con éxito."

class MetodoListView(ListView):
    model = Metodo
    template_name = 'servicios/metodo_list.html'
    context_object_name = 'metodos'

class MetodoCreateView(SuccessMessageMixin, CreateView):
    model = Metodo
    fields = ['codigo', 'nombre', 'descripcion']
    template_name = 'servicios/metodo_form.html'
    success_url = reverse_lazy('servicios:metodo_list')
    success_message = "El método de ensayo fue creado con éxito."

class MetodoUpdateView(SuccessMessageMixin, UpdateView):
    model = Metodo
    fields = ['codigo', 'nombre', 'descripcion']
    template_name = 'servicios/metodo_form.html'
    success_url = reverse_lazy('servicios:metodo_list')
    success_message = "El método de ensayo fue actualizado con éxito."
    
@require_POST
@login_required
@require_POST
@login_required
def crear_categoria_ajax(request):
    try:
        nombre = request.POST.get('nombre', '').strip()

        # Validaciones de seguridad
        if not nombre or len(nombre) < 2 or len(nombre) > 100:
            return JsonResponse({'status': 'error', 'message': 'Nombre debe tener entre 2 y 100 caracteres.'}, status=400)
        
        # Validar caracteres peligrosos
        import re
        if re.search(r'[<>]', nombre):
            logger.warning(f"Intento de XSS en crear_categoria_ajax por usuario {request.user.username}")
            return JsonResponse({'status': 'error', 'message': 'Caracteres no permitidos detectados.'}, status=400)

        # get_or_create evita errores si la categoría ya existe
        categoria, created = CategoriaServicio.objects.get_or_create(nombre=nombre)
        
        # Log de seguridad
        if created:
            logger.info(f"Categoría creada exitosamente: {nombre} por usuario {request.user.username}")
        else:
            logger.info(f"Categoría existente utilizada: {nombre} por usuario {request.user.username}")
        
        return JsonResponse({
            'status': 'success',
            'id': categoria.pk,
            'nombre': categoria.nombre,
            'nuevo': created
        })
    except Exception as e:
        logger.error(f"Error al crear categoría por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Error interno del servidor.'}, status=400)

@require_POST
@login_required
def crear_subcategoria_ajax(request):
    try:
        nombre = request.POST.get('nombre', '').strip()

        # Validaciones de seguridad
        if not nombre or len(nombre) < 2 or len(nombre) > 100:
            return JsonResponse({'status': 'error', 'message': 'Nombre debe tener entre 2 y 100 caracteres.'}, status=400)
        
        # Validar caracteres peligrosos
        import re
        if re.search(r'[<>]', nombre):
            logger.warning(f"Intento de XSS en crear_subcategoria_ajax por usuario {request.user.username}")
            return JsonResponse({'status': 'error', 'message': 'Caracteres no permitidos detectados.'}, status=400)

        subcategoria, created = Subcategoria.objects.get_or_create(nombre=nombre)
        
        # Log de seguridad
        if created:
            logger.info(f"Subcategoría creada exitosamente: {nombre} por usuario {request.user.username}")
        else:
            logger.info(f"Subcategoría existente utilizada: {nombre} por usuario {request.user.username}")
        
        return JsonResponse({
            'status': 'success',
            'id': subcategoria.pk,
            'nombre': subcategoria.nombre,
            'nuevo': created
        })
    except Exception as e:
        logger.error(f"Error al crear subcategoría por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Error interno del servidor.'}, status=400)
    
@login_required
def lista_cotizaciones(request):
    query = request.GET.get('q')
    estado_filtro = request.GET.get('estado') 
    fecha_inicio = request.GET.get('fecha_inicio') 
    fecha_fin = request.GET.get('fecha_fin')
    
    cotizaciones_list = Cotizacion.objects.select_related('cliente')\
                                          .filter(es_plantilla=False)\
                                          .order_by('-fecha_creacion')
    
    if not request.user.is_superuser:
        try:
            cliente_asociado = Cliente.objects.get(usuario=request.user) 
            cotizaciones_list = cotizaciones_list.filter(cliente=cliente_asociado)
        except Cliente.DoesNotExist:
            pass

    if query:
        cotizaciones_list = cotizaciones_list.filter(
            Q(numero_oferta__icontains=query) | 
            Q(cliente__razon_social__icontains=query) |
            Q(asunto_servicio__icontains=query)
        )

    if estado_filtro:
        cotizaciones_list = cotizaciones_list.filter(estado=estado_filtro)

    if fecha_inicio and fecha_fin:
        cotizaciones_list = cotizaciones_list.filter(fecha_generacion__range=[fecha_inicio, fecha_fin])

    paginator = Paginator(cotizaciones_list, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']

    context = {
        'cotizaciones': page_obj,
        'query': query,
        'estados_disponibles': Cotizacion.ESTADO_CHOICES, # ESTA LÍNEA ES VITAL
        'get_params': get_params.urlencode(),
    }
    return render(request, 'servicios/cotizacion_list.html', context)

def _guardar_snapshot_condiciones_cotizacion(cotizacion, secciones_data):
    if not isinstance(secciones_data, list):
        return

    cotizacion.condiciones_secciones.all().delete()

    total_items = 0

    for seccion_data in secciones_data:
        catalogo_seccion = None
        catalogo_seccion_id = seccion_data.get('catalogo_seccion_id')

        if catalogo_seccion_id:
            catalogo_seccion = CatalogoCondicionSeccion.objects.filter(pk=catalogo_seccion_id).first()

        seccion_snapshot = CotizacionCondicionSeccion.objects.create(
            cotizacion=cotizacion,
            catalogo_seccion=catalogo_seccion,
            codigo=seccion_data.get('codigo') or (catalogo_seccion.codigo if catalogo_seccion else ''),
            titulo=seccion_data.get('titulo') or (catalogo_seccion.titulo if catalogo_seccion else ''),
            tipo=seccion_data.get('tipo') or (catalogo_seccion.tipo if catalogo_seccion else 'lista'),
            orden=seccion_data.get('orden') or (catalogo_seccion.orden if catalogo_seccion else 1),
            seleccionada=bool(seccion_data.get('seleccionada', True)),
        )

        root_items = seccion_data.get('items', []) or []
        for item_data in root_items:
            _crear_item_snapshot_recursivo(
                seccion_snapshot=seccion_snapshot,
                item_data=item_data,
                parent_snapshot=None
            )

    total_items = CotizacionCondicionItem.objects.filter(
        seccion__cotizacion=cotizacion
    ).count()

    cotizacion.contenido_condiciones_configurado = total_items > 0
    cotizacion.save(update_fields=[
        'contenido_condiciones_configurado',
        'fecha_actualizacion',
    ])

@login_required
def crear_editar_cotizacion(request, pk=None):
    cotizacion = None
    error = None
    is_editing = pk is not None
    es_clonacion = request.GET.get('clon') == '1'

    if is_editing:
        cotizacion = get_object_or_404(
            Cotizacion.objects.prefetch_related(
                'grupos__detalles_items__servicio',
                'condiciones_secciones__items__children'
            ),
            pk=pk
        )
        if cotizacion.estado == 'Aceptada':
            messages.error(request, 'Esta cotización ya está aprobada y no se puede editar.')
            return redirect('servicios:lista_cotizaciones')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                cliente_id = request.POST.get('cliente')
                if not cliente_id:
                    raise ValueError("El campo Cliente es obligatorio.")

                cliente = Cliente.objects.get(pk=cliente_id)

                detalles_data_json = request.POST.get('detalles_json')
                if not detalles_data_json:
                    raise ValueError("El JSON de detalles está vacío.")

                detalles_data = json.loads(detalles_data_json)
                if not detalles_data:
                    raise ValueError("La cotización debe tener al menos un servicio.")

                condiciones_data_json = request.POST.get('condiciones_json', '').strip()
                condiciones_data = []
                if condiciones_data_json:
                    try:
                        condiciones_data = json.loads(condiciones_data_json)
                        if not isinstance(condiciones_data, list):
                            condiciones_data = []
                    except json.JSONDecodeError:
                        raise ValueError("El contenido de condiciones tiene un formato inválido.")

                if not is_editing:
                    cotizacion = Cotizacion(cliente=cliente)

                trabajador_id_post = request.POST.get('trabajador_responsable')
                if trabajador_id_post:
                    try:
                        cotizacion.trabajador_responsable = TrabajadorProfile.objects.get(pk=trabajador_id_post)
                    except TrabajadorProfile.DoesNotExist:
                        cotizacion.trabajador_responsable = None
                elif not is_editing:
                    try:
                        cotizacion.trabajador_responsable = TrabajadorProfile.objects.get(user=request.user)
                    except TrabajadorProfile.DoesNotExist:
                        cotizacion.trabajador_responsable = None
                elif is_editing and not trabajador_id_post:
                    cotizacion.trabajador_responsable = None

                cotizacion.cliente = cliente
                cotizacion.asunto_servicio = request.POST.get('asunto_servicio')
                cotizacion.proyecto_asociado = request.POST.get('proyecto_asociado')
                cotizacion.persona_contacto = request.POST.get('persona_contacto')
                cotizacion.correo_contacto = request.POST.get('correo_contacto')
                cotizacion.telefono_contacto = request.POST.get('telefono_contacto')

                cotizacion.es_plantilla = request.POST.get('es_plantilla') == 'on'
                cotizacion.nombre_plantilla = request.POST.get('nombre_plantilla') if cotizacion.es_plantilla else None

                fecha_generacion_str = request.POST.get('fecha_generacion')
                if fecha_generacion_str:
                    try:
                        cotizacion.fecha_generacion = date.fromisoformat(fecha_generacion_str)
                    except ValueError:
                        pass

                if not cotizacion.fecha_generacion:
                    cotizacion.fecha_generacion = date.today()

                if not cotizacion.es_plantilla:
                    cotizacion.estado = request.POST.get(
                        'estado',
                        cotizacion.estado if is_editing else 'Pendiente'
                    )

                servicio_general_pk = request.POST.get('servicio_general')
                if servicio_general_pk:
                    cotizacion.servicio_general = CategoriaServicio.objects.get(pk=servicio_general_pk)
                else:
                    cotizacion.servicio_general = None

                fp_seleccionada = request.POST.get('forma_pago')
                if fp_seleccionada == 'Personalizado':
                    fp_custom = request.POST.get('forma_pago_custom')
                    cotizacion.forma_pago = fp_custom if fp_custom else 'Personalizado'
                else:
                    cotizacion.forma_pago = fp_seleccionada

                try:
                    cotizacion.validez_oferta_dias = int(request.POST.get('validez_dias') or 30)
                    cotizacion.plazo_entrega_dias = int(request.POST.get('tiempo_entrega') or 30)
                except ValueError:
                    cotizacion.validez_oferta_dias = 30
                    cotizacion.plazo_entrega_dias = 30

                cotizacion.observaciones_condiciones = request.POST.get('observaciones_condiciones')

                tasa_igv_str = str(request.POST.get('tasa_igv', '0.18')).strip().replace(',', '.')
                cotizacion.tasa_igv = Decimal(tasa_igv_str)

                if not is_editing and not cotizacion.es_plantilla:
                    prefix = 'VCF-OTE'
                    year_part = str(cotizacion.fecha_generacion.year)
                    max_result = Cotizacion.objects.filter(
                        numero_oferta__startswith=f'{prefix}-{year_part}-'
                    ).aggregate(Max('numero_oferta'))

                    last_num_oferta = max_result.get('numero_oferta__max')
                    next_order_num = 1
                    if last_num_oferta:
                        try:
                            next_order_num = int(last_num_oferta.split('-')[-1]) + 1
                        except (IndexError, ValueError):
                            next_order_num = 1
                    cotizacion.numero_oferta = f'{prefix}-{year_part}-{str(next_order_num).zfill(3)}'
                elif cotizacion.es_plantilla:
                    cotizacion.numero_oferta = None

                cotizacion.save()

                if is_editing:
                    cotizacion.grupos.all().delete()

                grupo_actual = CotizacionGrupo.objects.create(
                    cotizacion=cotizacion,
                    nombre_grupo="ENSAYOS DE LABORATORIO",
                    orden=0
                )

                for index, item in enumerate(detalles_data):
                    tipo_fila = item.get('tipo_fila')

                    if tipo_fila in ['categoria', 'subcategoria']:
                        grupo_actual = CotizacionGrupo.objects.create(
                            cotizacion=cotizacion,
                            nombre_grupo=item.get('descripcion_especifica', '').upper(),
                            orden=index
                        )
                        continue

                    servicio_id = item.get('servicio_id')
                    if not servicio_id:
                        continue

                    servicio = Servicio.objects.get(pk=int(servicio_id))

                    partes_desc = []
                    cat_nom = item.get('categoria_nom', '')
                    subcat_nom = item.get('subcategoria_nom', '')

                    if cat_nom:
                        partes_desc.append(cat_nom.upper())
                    if subcat_nom:
                        partes_desc.append(subcat_nom)

                    desc_generada = f"{' - '.join(partes_desc)}: {servicio.nombre}" if partes_desc else servicio.nombre
                    desc_final = item.get('descripcion_especifica') or desc_generada

                    norma_txt = ""
                    norma_id = item.get('norma_id')
                    if norma_id and str(norma_id).isdigit():
                        n = Norma.objects.filter(pk=norma_id).first()
                        norma_txt = n.codigo if n else ""

                    metodo_txt = ""
                    metodo_id = item.get('metodo_id')
                    if metodo_id and str(metodo_id).isdigit():
                        m = Metodo.objects.filter(pk=metodo_id).first()
                        metodo_txt = m.codigo if m else ""

                    CotizacionDetalle.objects.create(
                        grupo=grupo_actual,
                        servicio=servicio,
                        norma_manual=norma_txt or item.get('norma_manual', ''),
                        metodo_manual=metodo_txt or item.get('metodo_manual', ''),
                        descripcion_especifica=desc_final,
                        unidad_medida=item.get('unidad_medida') or servicio.unidad_base,
                        cantidad=Decimal(str(item.get('cantidad', '1')).replace(',', '.')),
                        precio_unitario=Decimal(str(item.get('precio_unitario', '0')).replace(',', '.')),
                    )

                cotizacion.calcular_totales()
                cotizacion.save()

                if condiciones_data:
                    _guardar_snapshot_condiciones_cotizacion(cotizacion, condiciones_data)
                elif is_editing and cotizacion.condiciones_secciones.exists():
                    pass
                else:
                    cotizacion.condiciones_secciones.all().delete()
                    cotizacion.contenido_condiciones_configurado = False
                    cotizacion.save(update_fields=[
                        'contenido_condiciones_configurado',
                        'fecha_actualizacion',
                    ])

                identificador = cotizacion.nombre_plantilla if cotizacion.es_plantilla else cotizacion.numero_oferta
                messages.success(request, f"¡Cotización/Plantilla {identificador} procesada con éxito! ✅")
                return redirect('servicios:lista_cotizaciones')

        except Exception as e:
            error = f'Error al procesar: {str(e)}'
            if is_editing and pk:
                cotizacion = get_object_or_404(
                    Cotizacion.objects.prefetch_related(
                        'grupos__detalles_items__servicio',
                        'condiciones_secciones__items__children'
                    ),
                    pk=pk
                )

    clientes = Cliente.objects.all().order_by('razon_social')
    servicios_queryset = Servicio.objects.all().select_related('norma', 'metodo')
    categorias_principales = CategoriaServicio.objects.all()
    subcategorias_list = Subcategoria.objects.all()
    trabajadores = TrabajadorProfile.objects.all().select_related('user')
    plantillas = PlantillaCotizacion.objects.filter(activo=True).order_by('nombre_plantilla')

    servicios_list = []
    for s in servicios_queryset:
        servicios_list.append({
            'pk': s.pk,
            'nombre': s.nombre,
            'unidad_base': s.unidad_base,
            'precio_base': str(s.precio_base),
            'norma_codigo': s.norma.codigo if s.norma else 'N/A',
            'metodo_codigo': s.metodo.codigo if s.metodo else 'N/A',
            'norma_pk': s.norma.pk if s.norma else None,
            'metodo_pk': s.metodo.pk if s.metodo else None,
        })

    detalles_list = []
    if cotizacion:
        for grupo in cotizacion.grupos.all().order_by('orden'):
            if grupo.nombre_grupo != "ENSAYOS DE LABORATORIO":
                detalles_list.append({
                    'tipo_fila': 'categoria',
                    'descripcion_especifica': grupo.nombre_grupo
                })
            for detalle in grupo.detalles_items.all():
                detalles_list.append({
                    'tipo_fila': 'servicio',
                    'servicio_id': detalle.servicio.pk,
                    'descripcion_especifica': detalle.descripcion_especifica,
                    'norma_manual': detalle.norma_manual,
                    'metodo_manual': detalle.metodo_manual,
                    'unidad_medida': detalle.unidad_medida,
                    'cantidad': str(detalle.cantidad),
                    'precio_unitario': str(detalle.precio_unitario),
                    'total_detalle': str(detalle.total_detalle)
                })

    if cotizacion and cotizacion.condiciones_secciones.exists():
        condiciones_list = _obtener_condiciones_desde_snapshot(cotizacion)
    else:
        condiciones_list = _obtener_condiciones_desde_catalogo()

    context = {
        'cotizacion': cotizacion,
        'clientes': clientes,
        'servicios': servicios_queryset,
        'servicio_grupos': categorias_principales,
        'subcategorias': subcategorias_list,
        'servicios_con_detalles_json': json.dumps(servicios_list),
        'detalles_cotizacion_json': json.dumps(detalles_list),
        'condiciones_cotizacion_json': json.dumps(condiciones_list),
        'error': error,
        'estados_choices': Cotizacion.ESTADO_CHOICES,
        'forma_pago_choices': Cotizacion.FORMA_PAGO_CHOICES,
        'trabajadores': trabajadores,
        'es_clonacion': es_clonacion,
        'plantillas': plantillas,
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

def link_callback(uri, rel):
    """
    Convierte rutas de recursos HTML (CSS, imágenes) a rutas del sistema de archivos.
    Esto es necesario para que xhtml2pdf pueda incrustar archivos STATIC y MEDIA.
    """
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
    else:
        return uri 
        
    if not os.path.isfile(path):
        return uri
        
    return path

def header_footer_callback(canvas, doc):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    from reportlab.lib.units import cm

    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    
    header_text = "Código: VCF-LAB-FOR-001 | Fecha: 2025-03-05 | Versión: 06"
    header = Paragraph(header_text, style_normal)
    
    header.wrapOn(canvas, doc.width, doc.topMargin)
    header.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - 0.5 * cm) 


    footer_contact_text = "GRUPO VICAF SAC - Tel: +51 941 573 750 | Email: informes@grupovicaf.com"
    footer_contact = Paragraph(footer_contact_text, style_normal)
    
    footer_contact.wrapOn(canvas, doc.width, doc.bottomMargin)
    footer_contact.drawOn(canvas, doc.leftMargin, 1.0 * cm) 

    page_num = canvas.getPageNumber()
    page_text = f"Página {page_num}"
    
    canvas.drawString(doc.width + doc.leftMargin - 1.0 * cm, 1.0 * cm, page_text)


def _build_condiciones_pdf_data(cotizacion):
    secciones_pdf = []

    secciones = cotizacion.condiciones_secciones.prefetch_related(
        'items__children__children'
    ).all().order_by('orden', 'id')

    def build_selected_node(item):
        children_qs = item.children.all().order_by('orden', 'id')
        children_blocks = []

        for child in children_qs:
            child_block = build_selected_node(child)
            if child_block:
                children_blocks.append(child_block)

        has_self = bool(item.seleccionado and (item.texto_final or item.titulo))
        has_children = bool(children_blocks)

        if not has_self and not has_children:
            return None

        return {
            'titulo': item.titulo or '',
            'texto': item.texto_final or '',
            'children': children_blocks,
        }

    def flatten_blocks_for_pdf(block):
        rows = []

        if block['texto']:
            rows.append({
                'titulo': block['titulo'],
                'texto': block['texto'],
                'children': []
            })

        for child in block['children']:
            child_rows = flatten_blocks_for_pdf(child)
            rows.extend(child_rows)

        return rows

    for seccion in secciones:
        root_items = seccion.items.filter(parent__isnull=True).order_by('orden', 'id')

        bloques = []
        for item in root_items:
            node = build_selected_node(item)
            if node:
                bloques.extend(flatten_blocks_for_pdf(node))

        if not bloques:
            continue

        secciones_pdf.append({
            'codigo': seccion.codigo,
            'titulo': seccion.titulo,
            'tipo': seccion.tipo,
            'items': bloques,
        })

    return secciones_pdf

def reemplazar_tokens_condicion(texto, cotizacion):
    if not texto:
        return ''

    forma_pago_raw = getattr(cotizacion, 'forma_pago', '') or ''
    validez_oferta = getattr(cotizacion, 'validez_oferta_dias', '') or ''
    tiempo_entrega = getattr(cotizacion, 'plazo_entrega_dias', '') or ''

    forma_pago_map = {
        'Contado': 'Al contado',
        '15_dias': 'A 15 días',
        '30_dias': 'A 30 días',
        '60_dias': 'A 60 días',
        'Personalizado': 'Personalizado',
    }

    forma_pago = forma_pago_map.get(forma_pago_raw, forma_pago_raw)

    reemplazos = {
        '[[FORMA_PAGO]]': str(forma_pago),
        '[[VALIDEZ_OFERTA]]': str(validez_oferta),
        '[[TIEMPO_ENTREGA]]': str(tiempo_entrega),
    }

    texto_final = texto
    for token, valor in reemplazos.items():
        texto_final = texto_final.replace(token, valor)

    return texto_final

@login_required
def generar_pdf_cotizacion(request, pk):
    cotizacion = get_object_or_404(
        Cotizacion.objects.prefetch_related(
            'grupos__detalles_items__servicio__norma',
            'condiciones_secciones__items__children'
        ).select_related(
            'cliente',
            'trabajador_responsable',
            'servicio_general'
        ),
        pk=pk
    )

    jefe_laboratorio = cotizacion.trabajador_responsable
    if not jefe_laboratorio:
        try:
            jefe_laboratorio = TrabajadorProfile.objects.select_related('user').get(user__username='raquel')
        except (TrabajadorProfile.DoesNotExist, TrabajadorProfile.MultipleObjectsReturned):
            jefe_laboratorio = None

    tasa_igv_decimal = cotizacion.tasa_igv if cotizacion.tasa_igv is not None else Decimal('0.18')
    subtotal = cotizacion.subtotal if cotizacion.subtotal is not None else Decimal('0.00')
    igv_amount = cotizacion.impuesto_igv if cotizacion.impuesto_igv is not None else (subtotal * tasa_igv_decimal)
    monto_total = cotizacion.monto_total if cotizacion.monto_total is not None else (subtotal + igv_amount)
    igv_porcentaje = int(tasa_igv_decimal * 100)

    grupos_qs = cotizacion.grupos.all().order_by('orden', 'id')
    grupos_visibles = [g for g in grupos_qs if g.nombre_grupo != "ENSAYOS DE LABORATORIO"]

    if not grupos_visibles:
        grupos_visibles = list(grupos_qs)

    def serializar_items_pdf(items_queryset):
        items_pdf = []

        for item in items_queryset.order_by('orden', 'id'):
            if item.seleccionado and (item.texto_final or '').strip():
                items_pdf.append({
                    'texto': reemplazar_tokens_condicion(
                        item.texto_final.strip(),
                        cotizacion
                    )
                })

            children = item.children.all().order_by('orden', 'id')
            for child in children:
                if child.seleccionado and (child.texto_final or '').strip():
                    items_pdf.append({
                        'texto': reemplazar_tokens_condicion(
                            child.texto_final.strip(),
                            cotizacion
                        )
                    })

        return items_pdf

    secciones_condiciones_pdf = []

    if cotizacion.condiciones_secciones.exists():
        for seccion in cotizacion.condiciones_secciones.all().order_by('orden', 'id'):
            root_items = seccion.items.filter(parent__isnull=True)
            items_pdf = serializar_items_pdf(root_items)

            if items_pdf:
                secciones_condiciones_pdf.append({
                    'codigo': seccion.codigo,
                    'titulo': seccion.titulo,
                    'items': items_pdf
                })

    firma_aprobacion = None
    if jefe_laboratorio:
        posibles_campos = ['firma', 'firma_digital', 'imagen_firma']
        for campo in posibles_campos:
            archivo = getattr(jefe_laboratorio, campo, None)
            if archivo:
                try:
                    firma_aprobacion = request.build_absolute_uri(archivo.url)
                    break
                except Exception:
                    firma_aprobacion = None

    context = {
        'cotizacion': cotizacion,
        'grupos': grupos_visibles,
        'subtotal_final': subtotal,
        'igv_monto_final': igv_amount,
        'monto_total_final': monto_total,
        'igv_porcentaje': igv_porcentaje,
        'jefe_laboratorio': jefe_laboratorio,
        'secciones_condiciones_pdf': secciones_condiciones_pdf,
        'firma_aprobacion': firma_aprobacion,
    }

    template = get_template('servicios/cotizacion_pdf.html')
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    nombre_archivo = f"{cotizacion.numero_oferta}.pdf" if cotizacion.numero_oferta else f"Cotizacion_{pk}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

    pisa_status = pisa.CreatePDF(
        html,
        dest=response,
        link_callback=link_callback
    )

    if pisa_status.err:
        return HttpResponse('Tuvimos errores al generar el PDF.', status=500)

    return response

@login_required
@transaction.atomic 
def aprobar_cotizacion(request, pk):
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    if cotizacion.estado == 'Aceptada':
        messages.warning(request, f'La cotización {cotizacion.numero_oferta} ya fue aprobada anteriormente.')
        return redirect('proyectos:lista_proyectos_pendientes')

    if request.method == 'POST':
        codigo_voucher = request.POST.get('codigo_voucher', '').strip()
        monto_pagado_str = request.POST.get('monto_pagado', '0').strip()
        imagen_voucher = request.FILES.get('imagen_voucher')
        documento_firmado_cliente = request.FILES.get('documento_firmado_cliente')
        
        # Validaciones adicionales
        errores = []
        
        if not codigo_voucher or len(codigo_voucher) < 3:
            errores.append('El código de voucher debe tener al menos 3 caracteres.')
        
        if not monto_pagado_str:
            errores.append('El monto pagado es obligatorio.')
        else:
            try:
                monto_pagado = Decimal(monto_pagado_str.replace(',', ''))
                if monto_pagado <= 0:
                    errores.append('El monto pagado debe ser mayor a 0.')
                elif monto_pagado > cotizacion.monto_total * Decimal('1.1'):
                    errores.append('El monto pagado no puede exceder el 10% del monto cotizado.')
            except (TypeError, InvalidOperation, ValueError):
                errores.append('El monto pagado debe ser un número válido.')
        
        if not imagen_voucher:
            errores.append('El voucher de depósito es obligatorio.')
        else:
            # Validar tamaño del archivo (máx 10MB)
            if imagen_voucher.size > 10 * 1024 * 1024:
                errores.append('El voucher de depósito no puede exceder 10MB.')
            # Validar tipo de archivo
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
            if hasattr(imagen_voucher, 'content_type') and imagen_voucher.content_type not in allowed_types:
                errores.append('El voucher debe ser una imagen (JPG, PNG, GIF) o PDF.')
        
        if not documento_firmado_cliente:
            errores.append('El documento firmado es obligatorio.')
        else:
            # Validar tamaño del archivo (máx 10MB)
            if documento_firmado_cliente.size > 10 * 1024 * 1024:
                errores.append('El documento firmado no puede exceder 10MB.')
            # Validar que sea PDF
            if hasattr(documento_firmado_cliente, 'content_type') and documento_firmado_cliente.content_type != 'application/pdf':
                errores.append('El documento firmado debe ser un archivo PDF.')
        
        if errores:
            return render(request, 'servicios/aprobar_cotizacion.html', {
                'cotizacion': cotizacion,
                'error': ' '.join(errores),
                'codigo_voucher_value': codigo_voucher,
                'monto_pagado_value': monto_pagado_str,
            })

        try:
            # Verificar que no exista ya un voucher para esta cotización
            if Voucher.objects.filter(cotizacion=cotizacion).exists():
                return render(request, 'servicios/aprobar_cotizacion.html', {
                    'cotizacion': cotizacion,
                    'error': 'Esta cotización ya tiene un voucher registrado.',
                    'codigo_voucher_value': codigo_voucher,
                    'monto_pagado_value': monto_pagado_str,
                })
            
            voucher = Voucher.objects.create(
                cotizacion=cotizacion,
                codigo=codigo_voucher,
                monto_pagado=monto_pagado, 
                imagen=imagen_voucher,
                documento_firmado=documento_firmado_cliente 
            )
            
            cotizacion.estado = 'Aceptada'
            cotizacion.save()

            total_muestras = CotizacionDetalle.objects.filter(
                grupo__cotizacion=cotizacion
            ).aggregate(total=Sum('cantidad'))['total'] or 0
            
            nombre_proyecto = f"{cotizacion.cliente.razon_social} ({cotizacion.numero_oferta})"
            codigo_proyecto = f"P-{cotizacion.numero_oferta}" 
            
            proyecto, created = Proyecto.objects.get_or_create(
                cotizacion=cotizacion,
                defaults={
                    'nombre_proyecto': nombre_proyecto,
                    'codigo_proyecto': codigo_proyecto, 
                    'cliente': cotizacion.cliente,
                    'estado': 'PENDIENTE',
                    'descripcion_proyecto': f"Proyecto generado automáticamente desde cotización {cotizacion.numero_oferta}.",
                    'monto_cotizacion': cotizacion.monto_total,
                    'codigo_voucher': voucher.codigo,
                    'numero_muestras': total_muestras,
                }
            )
            
            if created:
                messages.success(request, f'Proyecto "{proyecto.nombre_proyecto}" creado exitosamente.')
            else:
                messages.info(request, f'Proyecto ya existía, se actualizó la información.')
            
            return redirect('proyectos:lista_proyectos_pendientes')
    
        except Exception as e:
            logger.error(f"Error en aprobación de cotización {pk}: {str(e)}", exc_info=True)
            return render(request, 'servicios/aprobar_cotizacion.html', {
                'cotizacion': cotizacion,
                'error': f'Ocurrió un error al procesar la aprobación: {str(e)}',
                'codigo_voucher_value': codigo_voucher,
                'monto_pagado_value': monto_pagado_str,
            })
    
    return render(request, 'servicios/aprobar_cotizacion.html', {'cotizacion': cotizacion})

@login_required
@login_required
def buscar_servicios_api(request):
    """
    API para la búsqueda de servicios que devuelve una respuesta JSON (autocompletado).
    """
    try:
        query = request.GET.get('q', '').strip()

        # Validaciones de seguridad
        if len(query) > 100:
            return JsonResponse({'error': 'La consulta no puede exceder 100 caracteres.'}, status=400)
        
        # Validar caracteres peligrosos
        import re
        if re.search(r'[<>]', query):
            logger.warning(f"Intento de XSS en buscar_servicios_api por usuario {request.user.username}")
            return JsonResponse({'error': 'Caracteres no permitidos detectados.'}, status=400)

        servicios = []
        if query:
            servicios_qs = Servicio.objects.filter(
                Q(nombre__icontains=query) | Q(codigo_facturacion__icontains=query)
            ).order_by('nombre')[:50]  # Limitar resultados
            
            for servicio in servicios_qs:
                servicios.append({
                    'pk': servicio.pk,
                    'nombre': servicio.nombre,
                    'codigo_facturacion': servicio.codigo_facturacion,
                    'unidad_base': servicio.unidad_base,
                    'precio_base': str(servicio.precio_base),
                })
        
        # Log de seguridad para consultas potencialmente sospechosas
        if len(query) > 50:
            logger.info(f"Consulta larga en buscar_servicios_api por usuario {request.user.username}: {query[:50]}...")
        
        return JsonResponse(servicios, safe=False)
    except Exception as e:
        logger.error(f"Error en buscar_servicios_api por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'error': 'Error interno del servidor.'}, status=500)

@login_required
def buscar_cotizaciones_api(request):
    """ Endpoint API para la búsqueda dinámica de cotizaciones. """
    
    try:
        query = request.GET.get('q', '').strip()

        # Validaciones de seguridad
        if len(query) > 100:
            return JsonResponse({'error': 'La consulta no puede exceder 100 caracteres.'}, status=400)
        
        # Validar caracteres peligrosos
        import re
        if re.search(r'[<>]', query):
            logger.warning(f"Intento de XSS en buscar_cotizaciones_api por usuario {request.user.username}")
            return JsonResponse({'error': 'Caracteres no permitidos detectados.'}, status=400)

        data = []

        if query:
            cotizaciones = Cotizacion.objects.filter(
                Q(numero_oferta__icontains=query) |
                Q(cliente__razon_social__icontains=query) |
                Q(asunto_servicio__icontains=query)
            ).select_related('cliente')[:50]  # Limitar resultados

            for cotizacion in cotizaciones:
                monto_total = cotizacion.monto_total if cotizacion.monto_total is not None else Decimal('0.00')
                
                data.append({
                    'pk': cotizacion.pk,
                    'numero_oferta': cotizacion.numero_oferta,
                    'fecha_generacion': cotizacion.fecha_generacion.strftime('%d/%m/%Y') if cotizacion.fecha_generacion else '',
                    'cliente_razon_social': cotizacion.cliente.razon_social,
                    'asunto_servicio': cotizacion.asunto_servicio or '',
                    'monto_total': str(monto_total),
                    'estado': cotizacion.estado,
                    'estado_display': cotizacion.get_estado_display(), 
                })

        # Log de seguridad para consultas potencialmente sospechosas
        if len(query) > 50:
            logger.info(f"Consulta larga en buscar_cotizaciones_api por usuario {request.user.username}: {query[:50]}...")
        
        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.error(f"Error en buscar_cotizaciones_api por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'error': 'Error interno del servidor.'}, status=500)

@login_required
def administracion_view(request):
    estados_disponibles = Cotizacion.ESTADO_CHOICES

    cotizaciones = Cotizacion.objects.select_related('cliente').all()


    q = request.GET.get('q')
    if q:
        cotizaciones = cotizaciones.filter(
            models.Q(numero_oferta__icontains=q) | 
            models.Q(asunto_servicio__icontains=q) |
            models.Q(cliente__razon_social__icontains=q)
        )

    estado_filtro = request.GET.get('estado')
    if estado_filtro:
        cotizaciones = cotizaciones.filter(estado=estado_filtro)

    f_inicio = request.GET.get('fecha_inicio')
    f_fin = request.GET.get('fecha_fin')
    if f_inicio and f_fin:
        cotizaciones = cotizaciones.filter(fecha_generacion__range=[f_inicio, f_fin])

    context = {
        'cotizaciones': cotizaciones,
        'estados_disponibles': estados_disponibles,
    }
    return render(request, 'administracion.html', context)

@login_required
def lista_plantillas(request):
    query = request.GET.get('q')
    plantillas_list = PlantillaCotizacion.objects.select_related('servicio_general')\
                                         .order_by('-fecha_creacion')

    if query:
        plantillas_list = plantillas_list.filter(
            Q(nombre_plantilla__icontains=query) |
            Q(asunto_referencial__icontains=query)
        )

    paginator = Paginator(plantillas_list, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'plantillas': page_obj,
        'query': query,
    }
    return render(request, 'servicios/plantillas_list.html', context)

@login_required
def crear_editar_plantilla(request, pk=None):
    plantilla = None
    error = None
    is_editing = pk is not None

    if is_editing:
        plantilla = get_object_or_404(
            PlantillaCotizacion.objects.prefetch_related(
                'grupos__detalles_items__servicio',
                'condiciones_secciones__items__children'
            ),
            pk=pk
        )
    else:
        plantilla = PlantillaCotizacion(activo=True)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                detalles_data_json = request.POST.get('detalles_json')
                if not detalles_data_json:
                    raise ValueError("El JSON de detalles está vacío.")

                detalles_data = json.loads(detalles_data_json)

                condiciones_data_json = request.POST.get('condiciones_json', '').strip()
                condiciones_data = []
                if condiciones_data_json:
                    try:
                        condiciones_data = json.loads(condiciones_data_json)
                        if not isinstance(condiciones_data, list):
                            condiciones_data = []
                    except json.JSONDecodeError:
                        raise ValueError("El contenido de condiciones tiene un formato inválido.")

                if is_editing:
                    plantilla = get_object_or_404(
                        PlantillaCotizacion.objects.prefetch_related(
                            'grupos__detalles_items__servicio',
                            'condiciones_secciones__items__children'
                        ),
                        pk=pk
                    )
                else:
                    plantilla = PlantillaCotizacion()

                plantilla.nombre_plantilla = request.POST.get('nombre')
                
                servicio_general_pk = request.POST.get('servicio_general')
                if servicio_general_pk:
                    plantilla.servicio_general = CategoriaServicio.objects.get(pk=servicio_general_pk)
                else:
                    plantilla.servicio_general = None

                plantilla.asunto_referencial = request.POST.get('asunto_servicio') or "COTIZACIÓN DE SERVICIOS"

                try:
                    plantilla.plazo_entrega_defecto = int(request.POST.get('tiempo_entrega') or 30)
                except (TypeError, ValueError):
                    plantilla.plazo_entrega_defecto = 30

                plantilla.forma_pago_defecto = request.POST.get('forma_pago') or 'Contado'
                plantilla.activo = request.POST.get('activo') == 'True'

                plantilla.save()

                if is_editing:
                    plantilla.grupos.all().delete()

                grupo_actual = PlantillaGrupo.objects.create(
                    plantilla=plantilla,
                    nombre_grupo="ENSAYOS DE LABORATORIO",
                    orden=0
                )

                for index, item in enumerate(detalles_data):
                    tipo_fila = item.get('tipo_fila')

                    if tipo_fila in ['categoria', 'subcategoria']:
                        grupo_actual = PlantillaGrupo.objects.create(
                            plantilla=plantilla,
                            nombre_grupo=item.get('descripcion_especifica', '').upper(),
                            orden=index + 1
                        )
                        continue

                    servicio_id = item.get('servicio_id')
                    if not servicio_id:
                        continue

                    servicio = Servicio.objects.get(pk=int(servicio_id))

                    PlantillaDetalle.objects.create(
                        grupo=grupo_actual,
                        servicio=servicio,
                        norma_manual=item.get('norma_nombre', ''),
                        descripcion_especifica=item.get('descripcion_especifica') or servicio.nombre,
                        unidad_medida=item.get('unidad_medida') or servicio.unidad_base,
                        cantidad=Decimal(str(item.get('cantidad', '1')).replace(',', '.')),
                        precio_unitario=Decimal(str(item.get('precio_unitario', '0')).replace(',', '.')),
                    )

                plantilla.calcular_totales()

                if condiciones_data:
                    _guardar_snapshot_condiciones_plantilla(plantilla, condiciones_data)
                else:
                    plantilla.condiciones_secciones.all().delete()

                messages.success(request, f"Plantilla '{plantilla.nombre_plantilla}' guardada.")
                return redirect('servicios:lista_plantillas')

        except Exception as e:
            error = f'Error: {str(e)}'
            if is_editing and pk:
                plantilla = get_object_or_404(
                    PlantillaCotizacion.objects.prefetch_related(
                        'grupos__detalles_items__servicio',
                        'condiciones_secciones__items__children'
                    ),
                    pk=pk
                )

    servicios_data = []
    for s in Servicio.objects.all().select_related('norma', 'metodo'):
        servicios_data.append({
            'pk': s.pk,
            'nombre': s.nombre,
            'precio_base': str(s.precio_base),
            'norma_codigo': s.norma.codigo if s.norma else '',
            'metodo_codigo': s.metodo.codigo if s.metodo else '',
            'unidad_base': s.unidad_base
        })

    detalles_list = []
    if plantilla and (is_editing or request.method == 'POST'):
        for grupo in plantilla.grupos.all().order_by('orden'):
            if grupo.nombre_grupo != "ENSAYOS DE LABORATORIO":
                detalles_list.append({
                    'tipo_fila': 'categoria',
                    'descripcion_especifica': grupo.nombre_grupo
                })

            for detalle in grupo.detalles_items.all():
                detalles_list.append({
                    'tipo_fila': 'servicio',
                    'servicio_id': detalle.servicio.pk,
                    'descripcion_especifica': detalle.descripcion_especifica,
                    'norma_nombre': detalle.norma_manual,
                    'unidad_medida': detalle.unidad_medida,
                    'cantidad': str(detalle.cantidad),
                    'precio_unitario': str(detalle.precio_unitario)
                })

    if plantilla and plantilla.pk and plantilla.condiciones_secciones.exists():
        condiciones_list = _obtener_condiciones_desde_snapshot_plantilla(plantilla)
    else:
        condiciones_list = _obtener_condiciones_desde_catalogo()

    context = {
        'plantilla': plantilla,
        'servicios_con_detalles_json': json.dumps(servicios_data),
        'servicio_grupos': CategoriaServicio.objects.all(),
        'subcategorias': Subcategoria.objects.all(),
        'detalles_cotizacion_json': json.dumps(detalles_list),
        'condiciones_plantilla_json': json.dumps(condiciones_list),
        'error': error,
    }
    return render(request, 'servicios/plantilla_form.html', context)

@login_required
def obtener_detalle_plantilla_json(request, pk):
    plantilla = get_object_or_404(
        PlantillaCotizacion.objects.prefetch_related(
            'grupos__detalles_items__servicio',
            'condiciones_secciones__items__children'
        ).select_related('servicio_general'),
        pk=pk
    )

    detalles_list = []
    for grupo in plantilla.grupos.all().order_by('orden'):
        if grupo.nombre_grupo != "ENSAYOS DE LABORATORIO":
            detalles_list.append({
                'tipo_fila': 'categoria',
                'descripcion_especifica': grupo.nombre_grupo
            })

        for detalle in grupo.detalles_items.all():
            detalles_list.append({
                'tipo_fila': 'servicio',
                'servicio_id': detalle.servicio.pk,
                'descripcion_especifica': detalle.descripcion_especifica,
                'norma_nombre': detalle.norma_manual,
                'unidad_medida': detalle.unidad_medida,
                'cantidad': str(detalle.cantidad),
                'precio_unitario': str(detalle.precio_unitario)
            })

    if plantilla.condiciones_secciones.exists():
        condiciones_list = _obtener_condiciones_desde_snapshot_plantilla(plantilla)
    else:
        condiciones_list = _obtener_condiciones_desde_catalogo()

    return JsonResponse({
        'success': True,
        'plantilla': {
            'id': plantilla.id,
            'nombre_plantilla': plantilla.nombre_plantilla,
            'asunto_referencial': plantilla.asunto_referencial,
            'forma_pago_defecto': plantilla.forma_pago_defecto,
            'plazo_entrega_defecto': plantilla.plazo_entrega_defecto,
            'servicio_general_id': plantilla.servicio_general_id,
        },
        'detalles': detalles_list,
        'condiciones': condiciones_list,
    })
        

def _parse_json_request_body(request):
    """
    Intenta leer JSON del body.
    Si no existe, intenta leerlo desde request.POST['payload'].
    """
    try:
        if request.body:
            return json.loads(request.body.decode('utf-8'))
    except Exception:
        pass

    payload = request.POST.get('payload')
    if payload:
        try:
            return json.loads(payload)
        except Exception:
            pass

    return {}

def _serializar_catalogo_item(item):
    """
    Serializa un ítem del catálogo con sus hijos.
    """
    children = item.children.filter(activo=True).order_by('orden', 'id')

    return {
        'id': item.id,
        'catalogo_item_id': item.id,
        'parent_id': item.parent_id,
        'tipo_nodo': item.tipo_nodo,
        'titulo': item.titulo or '',
        'texto': item.texto or '',
        'texto_base': item.texto or '',
        'texto_final': item.texto or '',
        'orden': item.orden,
        'nivel': item.nivel,
        'seleccionado': item.seleccionado_por_defecto or item.es_obligatorio,
        'es_obligatorio': item.es_obligatorio,
        'editable_en_cotizacion': item.editable_en_cotizacion,
        'fue_editado': False,
        'children': [_serializar_catalogo_item(child) for child in children],
    }

def _serializar_snapshot_item(item):
    """
    Serializa un ítem snapshot con sus hijos.
    """
    children = item.children.all().order_by('orden', 'id')

    return {
        'id': item.id,
        'catalogo_item_id': item.catalogo_item_id,
        'parent_id': item.parent_id,
        'tipo_nodo': item.tipo_nodo,
        'titulo': item.titulo or '',
        'texto': item.texto_final or '',
        'texto_base': item.texto_base or '',
        'texto_final': item.texto_final or '',
        'orden': item.orden,
        'nivel': item.nivel,
        'seleccionado': item.seleccionado,
        'es_obligatorio': item.es_obligatorio,
        'editable_en_cotizacion': item.editable_en_cotizacion,
        'fue_editado': item.fue_editado,
        'children': [_serializar_snapshot_item(child) for child in children],
    }


def _obtener_condiciones_desde_snapshot(cotizacion):
    """
    Devuelve la estructura de condiciones desde el snapshot guardado
    de la cotización.
    """
    secciones = cotizacion.condiciones_secciones.all().order_by('orden', 'id')
    resultado = []

    for seccion in secciones:
        root_items = seccion.items.filter(parent__isnull=True).order_by('orden', 'id')
        resultado.append({
            'id': seccion.id,
            'catalogo_seccion_id': seccion.catalogo_seccion_id,
            'codigo': seccion.codigo,
            'titulo': seccion.titulo,
            'tipo': seccion.tipo,
            'orden': seccion.orden,
            'seleccionada': seccion.seleccionada,
            'items': [_serializar_snapshot_item(item) for item in root_items],
        })

    return resultado


def _obtener_condiciones_desde_catalogo():
    secciones = CatalogoCondicionSeccion.objects.filter(activo=True).order_by('orden')

    resultado = []

    for seccion in secciones:
        items_root = CatalogoCondicionItem.objects.filter(
            seccion=seccion,
            parent__isnull=True,
            activo=True
        ).order_by('orden')

        def build_item(item):
            children = CatalogoCondicionItem.objects.filter(
                parent=item,
                activo=True
            ).order_by('orden')

            return {
                "id": item.id,
                "titulo": item.titulo,
                "texto_base": item.texto,
                "texto_final": item.texto,
                "seleccionado": item.seleccionado_por_defecto,
                "editable_en_cotizacion": item.editable_en_cotizacion,
                "es_obligatorio": item.es_obligatorio,
                "tipo_nodo": item.tipo_nodo,
                "children": [build_item(c) for c in children]
            }

        resultado.append({
            "catalogo_seccion_id": seccion.id,
            "codigo": seccion.codigo,
            "titulo": seccion.titulo,
            "tipo": seccion.tipo,
            "orden": seccion.orden,
            "seleccionada": True,
            "items": [build_item(i) for i in items_root]
        })

    return resultado

def _crear_item_snapshot_recursivo(seccion_snapshot, item_data, parent_snapshot=None):
    """
    Crea un ítem snapshot y sus hijos de forma recursiva.
    """
    catalogo_item = None
    catalogo_item_id = item_data.get('catalogo_item_id')

    if catalogo_item_id:
        catalogo_item = CatalogoCondicionItem.objects.filter(pk=catalogo_item_id).first()

    texto_base = item_data.get('texto_base')
    texto_final = item_data.get('texto_final')

    if not texto_base and catalogo_item:
        texto_base = catalogo_item.texto

    if not texto_final:
        texto_final = texto_base or item_data.get('texto') or ''

    snapshot_item = CotizacionCondicionItem.objects.create(
        seccion=seccion_snapshot,
        catalogo_item=catalogo_item,
        parent=parent_snapshot,
        tipo_nodo=item_data.get('tipo_nodo') or (catalogo_item.tipo_nodo if catalogo_item else 'item'),
        titulo=item_data.get('titulo') or (catalogo_item.titulo if catalogo_item else ''),
        texto_base=texto_base or '',
        texto_final=texto_final or '',
        orden=item_data.get('orden') or (catalogo_item.orden if catalogo_item else 1),
        nivel=item_data.get('nivel') if item_data.get('nivel') is not None else (catalogo_item.nivel if catalogo_item else 0),
        seleccionado=bool(item_data.get('seleccionado', False)),
        es_obligatorio=bool(
            item_data.get('es_obligatorio', False) or
            (catalogo_item.es_obligatorio if catalogo_item else False)
        ),
        editable_en_cotizacion=bool(
            item_data.get('editable_en_cotizacion', True) if item_data.get('editable_en_cotizacion') is not None
            else (catalogo_item.editable_en_cotizacion if catalogo_item else True)
        ),
    )

    children = item_data.get('children', []) or []
    for child in children:
        _crear_item_snapshot_recursivo(
            seccion_snapshot=seccion_snapshot,
            item_data=child,
            parent_snapshot=snapshot_item
        )

    return snapshot_item


@login_required
def condiciones_cotizacion_json(request, pk):
    """
    Devuelve el catálogo de condiciones para el modal.
    Si la cotización ya tiene snapshot, devuelve lo guardado.
    Si no tiene snapshot, devuelve el catálogo por defecto.
    """
    try:
        cotizacion = get_object_or_404(
            Cotizacion.objects.prefetch_related(
                'condiciones_secciones__items__children'
            ),
            pk=pk
        )

        tiene_snapshot = cotizacion.condiciones_secciones.exists()

        if tiene_snapshot:
            secciones = _obtener_condiciones_desde_snapshot(cotizacion)
        else:
            secciones = _obtener_condiciones_desde_catalogo()

        return JsonResponse({
            'success': True,
            'cotizacion_id': cotizacion.id,
            'numero_oferta': cotizacion.numero_oferta,
            'contenido_condiciones_configurado': cotizacion.contenido_condiciones_configurado,
            'contenido_condiciones_bloqueado': cotizacion.contenido_condiciones_bloqueado,
            'puede_editar': cotizacion.puede_editar_contenido_condiciones(),
            'usa_snapshot': tiene_snapshot,
            'secciones': secciones,
        })

    except Exception as e:
        logger.error(f"Error en condiciones_cotizacion_json para cotización {pk}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'No se pudo cargar la configuración de condiciones: {str(e)}'
        }, status=500)


@login_required
@require_POST
@transaction.atomic
def guardar_condiciones_cotizacion_json(request, pk):
    """
    Guarda el snapshot de condiciones seleccionado para la cotización.
    Reemplaza completamente el snapshot anterior si existe.
    """
    try:
        cotizacion = get_object_or_404(Cotizacion, pk=pk)

        if not cotizacion.puede_editar_contenido_condiciones():
            return JsonResponse({
                'success': False,
                'error': 'La cotización no permite editar el contenido de condiciones.'
            }, status=403)

        payload = _parse_json_request_body(request)
        secciones_data = payload.get('secciones', [])

        if not isinstance(secciones_data, list):
            return JsonResponse({
                'success': False,
                'error': 'El formato de secciones es inválido.'
            }, status=400)

        # Limpieza del snapshot anterior
        cotizacion.condiciones_secciones.all().delete()

        total_secciones = 0
        total_items = 0

        for seccion_data in secciones_data:
            catalogo_seccion = None
            catalogo_seccion_id = seccion_data.get('catalogo_seccion_id')

            if catalogo_seccion_id:
                catalogo_seccion = CatalogoCondicionSeccion.objects.filter(pk=catalogo_seccion_id).first()

            seccion_snapshot = CotizacionCondicionSeccion.objects.create(
                cotizacion=cotizacion,
                catalogo_seccion=catalogo_seccion,
                codigo=seccion_data.get('codigo') or (catalogo_seccion.codigo if catalogo_seccion else ''),
                titulo=seccion_data.get('titulo') or (catalogo_seccion.titulo if catalogo_seccion else ''),
                tipo=seccion_data.get('tipo') or (catalogo_seccion.tipo if catalogo_seccion else 'lista'),
                orden=seccion_data.get('orden') or (catalogo_seccion.orden if catalogo_seccion else 1),
                seleccionada=bool(seccion_data.get('seleccionada', True)),
            )
            total_secciones += 1

            root_items = seccion_data.get('items', []) or []
            for item_data in root_items:
                _crear_item_snapshot_recursivo(
                    seccion_snapshot=seccion_snapshot,
                    item_data=item_data,
                    parent_snapshot=None
                )

        total_items = CotizacionCondicionItem.objects.filter(
            seccion__cotizacion=cotizacion
        ).count()

        cotizacion.contenido_condiciones_configurado = True
        cotizacion.save(update_fields=[
            'contenido_condiciones_configurado',
            'fecha_actualizacion',
        ])

        return JsonResponse({
            'success': True,
            'message': 'Las condiciones de la cotización fueron guardadas correctamente.',
            'cotizacion_id': cotizacion.id,
            'total_secciones': total_secciones,
            'total_items': total_items,
        })

    except Exception as e:
        logger.error(f"Error en guardar_condiciones_cotizacion_json para cotización {pk}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'No se pudieron guardar las condiciones: {str(e)}'
        }, status=500)


@login_required
def resumen_condiciones_cotizacion_json(request, pk):
    """
    Devuelve un resumen por sección para mostrar en la UI.
    """
    try:
        cotizacion = get_object_or_404(
            Cotizacion.objects.prefetch_related('condiciones_secciones__items'),
            pk=pk
        )

        resumen = []
        for seccion in cotizacion.condiciones_secciones.all().order_by('orden', 'id'):
            items_seleccionados = seccion.items.filter(seleccionado=True, tipo_nodo='item').count()
            grupos = seccion.items.filter(tipo_nodo='grupo').count()

            resumen.append({
                'codigo': seccion.codigo,
                'titulo': seccion.titulo,
                'tipo': seccion.tipo,
                'seleccionada': seccion.seleccionada,
                'items_seleccionados': items_seleccionados,
                'grupos': grupos,
            })

        return JsonResponse({
            'success': True,
            'cotizacion_id': cotizacion.id,
            'configurado': cotizacion.contenido_condiciones_configurado,
            'bloqueado': cotizacion.contenido_condiciones_bloqueado,
            'resumen': resumen,
        })

    except Exception as e:
        logger.error(f"Error en resumen_condiciones_cotizacion_json para cotización {pk}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'No se pudo obtener el resumen: {str(e)}'
        }, status=500)
        
def _obtener_condiciones_desde_snapshot_plantilla(plantilla):
    secciones = plantilla.condiciones_secciones.all().order_by('orden', 'id')
    resultado = []

    for seccion in secciones:
        items_root = seccion.items.filter(parent__isnull=True).order_by('orden', 'id')
        resultado.append({
            'id': seccion.id,
            'catalogo_seccion_id': seccion.catalogo_seccion_id,
            'codigo': seccion.codigo,
            'titulo': seccion.titulo,
            'tipo': seccion.tipo,
            'orden': seccion.orden,
            'seleccionada': seccion.seleccionada,
            'items': [_serializar_snapshot_item_plantilla(item) for item in items_root],
        })

    return resultado


def _serializar_snapshot_item_plantilla(item):
    children = item.children.all().order_by('orden', 'id')

    return {
        'id': item.id,
        'catalogo_item_id': item.catalogo_item_id,
        'parent_id': item.parent_id,
        'tipo_nodo': item.tipo_nodo,
        'titulo': item.titulo or '',
        'texto': item.texto_final or '',
        'texto_base': item.texto_base or '',
        'texto_final': item.texto_final or '',
        'orden': item.orden,
        'nivel': item.nivel,
        'seleccionado': item.seleccionado,
        'es_obligatorio': item.es_obligatorio,
        'editable_en_cotizacion': item.editable_en_cotizacion,
        'fue_editado': item.fue_editado,
        'children': [_serializar_snapshot_item_plantilla(child) for child in children],
    }


def _crear_item_snapshot_recursivo_plantilla(seccion_snapshot, item_data, parent_snapshot=None):
    catalogo_item = None
    catalogo_item_id = item_data.get('catalogo_item_id')

    if catalogo_item_id:
        catalogo_item = CatalogoCondicionItem.objects.filter(pk=catalogo_item_id).first()

    texto_base = item_data.get('texto_base') or (catalogo_item.texto if catalogo_item else '')
    texto_final = item_data.get('texto_final') or texto_base

    snapshot_item = PlantillaCondicionItem.objects.create(
        seccion=seccion_snapshot,
        catalogo_item=catalogo_item,
        parent=parent_snapshot,
        tipo_nodo=item_data.get('tipo_nodo') or (catalogo_item.tipo_nodo if catalogo_item else 'item'),
        titulo=item_data.get('titulo') or (catalogo_item.titulo if catalogo_item else ''),
        texto_base=texto_base or '',
        texto_final=texto_final or '',
        orden=item_data.get('orden') or (catalogo_item.orden if catalogo_item else 1),
        nivel=item_data.get('nivel') if item_data.get('nivel') is not None else (catalogo_item.nivel if catalogo_item else 0),
        seleccionado=bool(item_data.get('seleccionado', False)),
        es_obligatorio=bool(
            item_data.get('es_obligatorio', False) or
            (catalogo_item.es_obligatorio if catalogo_item else False)
        ),
        editable_en_cotizacion=bool(
            item_data.get('editable_en_cotizacion', True) if item_data.get('editable_en_cotizacion') is not None
            else (catalogo_item.editable_en_cotizacion if catalogo_item else True)
        ),
    )

    children = item_data.get('children', []) or []
    for child in children:
        _crear_item_snapshot_recursivo_plantilla(
            seccion_snapshot=seccion_snapshot,
            item_data=child,
            parent_snapshot=snapshot_item
        )

    return snapshot_item


def _guardar_snapshot_condiciones_plantilla(plantilla, secciones_data):
    if not isinstance(secciones_data, list):
        return

    plantilla.condiciones_secciones.all().delete()

    for seccion_data in secciones_data:
        catalogo_seccion = None
        catalogo_seccion_id = seccion_data.get('catalogo_seccion_id')

        if catalogo_seccion_id:
            catalogo_seccion = CatalogoCondicionSeccion.objects.filter(pk=catalogo_seccion_id).first()

        seccion_snapshot = PlantillaCondicionSeccion.objects.create(
            plantilla=plantilla,
            catalogo_seccion=catalogo_seccion,
            codigo=seccion_data.get('codigo') or (catalogo_seccion.codigo if catalogo_seccion else ''),
            titulo=seccion_data.get('titulo') or (catalogo_seccion.titulo if catalogo_seccion else ''),
            tipo=seccion_data.get('tipo') or (catalogo_seccion.tipo if catalogo_seccion else 'lista'),
            orden=seccion_data.get('orden') or (catalogo_seccion.orden if catalogo_seccion else 1),
            seleccionada=bool(seccion_data.get('seleccionada', False)),
        )

        root_items = seccion_data.get('items', []) or []
        for item_data in root_items:
            _crear_item_snapshot_recursivo_plantilla(
                seccion_snapshot=seccion_snapshot,
                item_data=item_data,
                parent_snapshot=None
            )

@login_required
def condiciones_plantilla_json(request, pk):
    try:
        plantilla = get_object_or_404(
            PlantillaCotizacion.objects.prefetch_related(
                'condiciones_secciones__items__children'
            ),
            pk=pk
        )

        tiene_snapshot = plantilla.condiciones_secciones.exists()

        if tiene_snapshot:
            secciones = _obtener_condiciones_desde_snapshot_plantilla(plantilla)
        else:
            secciones = _obtener_condiciones_desde_catalogo()

        return JsonResponse({
            'success': True,
            'plantilla_id': plantilla.id,
            'nombre_plantilla': plantilla.nombre_plantilla,
            'usa_snapshot': tiene_snapshot,
            'secciones': secciones,
        })
    except Exception as e:
        logger.error(f"Error en condiciones_plantilla_json para plantilla {pk}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'No se pudo cargar la configuración de condiciones: {str(e)}'
        }, status=500)


@login_required
@require_POST
@transaction.atomic
def guardar_condiciones_plantilla_json(request, pk):
    try:
        plantilla = get_object_or_404(PlantillaCotizacion, pk=pk)

        payload = _parse_json_request_body(request)
        secciones_data = payload.get('secciones', [])

        if not isinstance(secciones_data, list):
            return JsonResponse({
                'success': False,
                'error': 'El formato de secciones es inválido.'
            }, status=400)

        plantilla.condiciones_secciones.all().delete()

        total_secciones = 0
        total_items = 0

        for seccion_data in secciones_data:
            catalogo_seccion = None
            catalogo_seccion_id = seccion_data.get('catalogo_seccion_id')

            if catalogo_seccion_id:
                catalogo_seccion = CatalogoCondicionSeccion.objects.filter(pk=catalogo_seccion_id).first()

            seccion_snapshot = PlantillaCondicionSeccion.objects.create(
                plantilla=plantilla,
                catalogo_seccion=catalogo_seccion,
                codigo=seccion_data.get('codigo') or (catalogo_seccion.codigo if catalogo_seccion else ''),
                titulo=seccion_data.get('titulo') or (catalogo_seccion.titulo if catalogo_seccion else ''),
                tipo=seccion_data.get('tipo') or (catalogo_seccion.tipo if catalogo_seccion else 'lista'),
                orden=seccion_data.get('orden') or (catalogo_seccion.orden if catalogo_seccion else 1),
                seleccionada=bool(seccion_data.get('seleccionada', False)),
            )
            total_secciones += 1

            for item_data in seccion_data.get('items', []) or []:
                _crear_item_snapshot_recursivo_plantilla(
                    seccion_snapshot=seccion_snapshot,
                    item_data=item_data,
                    parent_snapshot=None
                )

        total_items = PlantillaCondicionItem.objects.filter(
            seccion__plantilla=plantilla
        ).count()

        return JsonResponse({
            'success': True,
            'message': 'Las condiciones de la plantilla fueron guardadas correctamente.',
            'plantilla_id': plantilla.id,
            'total_secciones': total_secciones,
            'total_items': total_items,
        })

    except Exception as e:
        logger.error(f"Error en guardar_condiciones_plantilla_json para plantilla {pk}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'No se pudieron guardar las condiciones: {str(e)}'
        }, status=500)


@login_required
def resumen_condiciones_plantilla_json(request, pk):
    try:
        plantilla = get_object_or_404(
            PlantillaCotizacion.objects.prefetch_related('condiciones_secciones__items'),
            pk=pk
        )

        resumen = []
        for seccion in plantilla.condiciones_secciones.all().order_by('orden', 'id'):
            items_seleccionados = seccion.items.filter(seleccionado=True, tipo_nodo='item').count()
            grupos = seccion.items.filter(tipo_nodo='grupo').count()

            resumen.append({
                'codigo': seccion.codigo,
                'titulo': seccion.titulo,
                'tipo': seccion.tipo,
                'seleccionada': seccion.seleccionada,
                'items_seleccionados': items_seleccionados,
                'grupos': grupos,
            })

        return JsonResponse({
            'success': True,
            'plantilla_id': plantilla.id,
            'resumen': resumen,
        })

    except Exception as e:
        logger.error(f"Error en resumen_condiciones_plantilla_json para plantilla {pk}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'No se pudo obtener el resumen: {str(e)}'
        }, status=500)