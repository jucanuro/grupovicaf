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
    Subcategoria, CotizacionGrupo
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
            # 1. Validación de Precio
            precio_base_str = request.POST.get('precio_base', '0').replace(',', '.')
            try:
                precio_base = Decimal(precio_base_str)
            except Exception:
                raise ValueError("El campo 'Precio Base' debe ser un número válido.")

            # 2. Preparar Datos (Sin subcategoría FK)
            data_servicio = {
                'nombre': request.POST.get('nombre'),
                'codigo_facturacion': request.POST.get('codigo_facturacion'),
                'precio_base': precio_base,
                'unidad_base': request.POST.get('unidad_base', 'Ensayo'),
                'esta_acreditado': request.POST.get('esta_acreditado') == 'on',
                'norma_id': request.POST.get('norma') or None,
                'metodo_id': request.POST.get('metodo') or None,
            }

            if not data_servicio['nombre'] or not data_servicio['codigo_facturacion']:
                raise ValueError("Nombre y Código de Facturación son obligatorios.")

            # 3. Crear o Actualizar
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

def crear_norma_ajax(request):
    if request.method == 'POST':
        codigo = request.POST.get('codigo_norma')
        nombre = request.POST.get('nombre_norma')
        descripcion = request.POST.get('descripcion_norma', '')

        if not codigo or not nombre:
            return JsonResponse({'success': False, 'error': 'Código y Nombre son obligatorios.'})

        try:
            norma = Norma.objects.create(
                codigo=codigo,
                nombre=nombre,
                descripcion=descripcion
            )
            return JsonResponse({
                'success': True,
                'id': norma.id,
                'codigo': norma.codigo  # Usamos el código para mostrarlo en el select
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})

def crear_metodo_ajax(request):
    if request.method == 'POST':
        codigo = request.POST.get('codigo_metodo')
        nombre = request.POST.get('nombre_metodo')
        descripcion = request.POST.get('descripcion_metodo', '')

        if not codigo or not nombre:
            return JsonResponse({'success': False, 'error': 'Código y Nombre son obligatorios.'})

        try:
            metodo = Metodo.objects.create(
                codigo=codigo,
                nombre=nombre,
                descripcion=descripcion
            )
            return JsonResponse({
                'success': True,
                'id': metodo.id,
                'nombre': metodo.nombre,
                'codigo': metodo.codigo
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
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
def crear_categoria_ajax(request):
    nombre = request.POST.get('nombre', '').strip()
    if not nombre:
        return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'}, status=400)
    
    try:
        # get_or_create evita errores si la categoría ya existe
        categoria, created = CategoriaServicio.objects.get_or_create(nombre=nombre)
        return JsonResponse({
            'status': 'success',
            'id': categoria.pk,
            'nombre': categoria.nombre,
            'nuevo': created
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
def crear_subcategoria_ajax(request):
    nombre = request.POST.get('nombre', '').strip()
    if not nombre:
        return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'}, status=400)

    try:
        subcategoria, created = Subcategoria.objects.get_or_create(nombre=nombre)
        return JsonResponse({
            'status': 'success',
            'id': subcategoria.pk,
            'nombre': subcategoria.nombre,
            'nuevo': created
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
@login_required
def lista_cotizaciones(request):
    query = request.GET.get('q')
    
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
            Q(estado__icontains=query)
        )

    paginator = Paginator(cotizaciones_list, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'cotizaciones': page_obj,
        'query': query,
    }
    return render(request, 'servicios/cotizacion_list.html', context)

@login_required
def lista_plantillas(request):
    query = request.GET.get('q')
    
    plantillas_list = Cotizacion.objects.select_related('cliente')\
                                        .filter(es_plantilla=True)\
                                        .order_by('-fecha_creacion')

    if query:
        plantillas_list = plantillas_list.filter(
            Q(nombre_plantilla__icontains=query) |
            Q(asunto_servicio__icontains=query)
        )

    paginator = Paginator(plantillas_list, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'plantillas': page_obj,
        'query': query,
    }
    return render(request, 'servicios/plantillas_list.html', context)

@login_required
def crear_editar_cotizacion(request, pk=None):
    cotizacion = None
    error = None
    is_editing = pk is not None
    es_clonacion = request.GET.get('clon') == '1'

    if is_editing:
        cotizacion = get_object_or_404(Cotizacion, pk=pk) 

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
                
                if cotizacion.es_plantilla:
                    cotizacion.estado = 'Plantilla'
                else:
                    cotizacion.estado = request.POST.get('estado', cotizacion.estado if is_editing else 'Pendiente')
                
                cotizacion.aprobada_por_cliente = request.POST.get('aprobada_por_cliente') == 'on'

                servicio_general_pk = request.POST.get('servicio_general')
                if servicio_general_pk:
                    cotizacion.servicio_general = CategoriaServicio.objects.get(pk=servicio_general_pk)

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
                    if not servicio_id: continue
                    
                    servicio = Servicio.objects.get(pk=int(servicio_id))
                    partes_desc = []
                    cat_nom = item.get('categoria_nom', '') 
                    subcat_nom = item.get('subcategoria_nom', '') 
                    
                    if cat_nom: partes_desc.append(cat_nom.upper())
                    if subcat_nom: partes_desc.append(subcat_nom)
                    
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

                identificador = cotizacion.nombre_plantilla if cotizacion.es_plantilla else cotizacion.numero_oferta
                messages.success(request, f"¡Cotización/Plantilla {identificador} procesada con éxito! ✅")
                return redirect('servicios:lista_cotizaciones')

        except Exception as e:
            error = f'Error al procesar: {str(e)}'
            if is_editing and pk:
                cotizacion = get_object_or_404(Cotizacion, pk=pk)

    clientes = Cliente.objects.all().order_by('razon_social')
    servicios_queryset = Servicio.objects.all().select_related('norma', 'metodo')
    categorias_principales = CategoriaServicio.objects.all()
    subcategorias_list = Subcategoria.objects.all()
    trabajadores = TrabajadorProfile.objects.all().select_related('user')

    servicios_list = []
    for s in servicios_queryset:
        servicios_list.append({
            'pk': s.pk, 'nombre': s.nombre, 'unidad_base': s.unidad_base,
            'precio_base': str(s.precio_base), 
            'norma_codigo': s.norma.codigo if s.norma else 'N/A',
            'metodo_codigo': s.metodo.codigo if s.metodo else 'N/A',
        })

    detalles_list = []
    if cotizacion:
        for grupo in cotizacion.grupos.all().order_by('orden'):
            if grupo.nombre_grupo != "ENSAYOS DE LABORATORIO":
                detalles_list.append({'tipo_fila': 'categoria', 'descripcion_especifica': grupo.nombre_grupo})
            for detalle in grupo.detalles_items.all():
                detalles_list.append({
                    'tipo_fila': 'servicio', 'servicio_id': detalle.servicio.pk,
                    'descripcion_especifica': detalle.descripcion_especifica,
                    'norma_manual': detalle.norma_manual, 'metodo_manual': detalle.metodo_manual,
                    'unidad_medida': detalle.unidad_medida, 'cantidad': str(detalle.cantidad),
                    'precio_unitario': str(detalle.precio_unitario), 'total_detalle': str(detalle.total_detalle)
                })
    
    context = {
        'cotizacion': cotizacion,
        'clientes': clientes,
        'servicios': servicios_queryset,
        'servicio_grupos': categorias_principales, 
        'subcategorias': subcategorias_list,        
        'servicios_con_detalles_json': json.dumps(servicios_list),
        'detalles_cotizacion_json': json.dumps(detalles_list), 
        'error': error,
        'estados_choices': Cotizacion.ESTADO_CHOICES,
        'forma_pago_choices': Cotizacion.FORMA_PAGO_CHOICES,
        'trabajadores': trabajadores,
        'es_clonacion': es_clonacion, 
    }
    return render(request, 'servicios/cotizaciones_form.html', context)

crear_cotizacion = crear_editar_cotizacion
editar_cotizacion = crear_editar_cotizacion

@login_required
def usar_plantilla(request, pk):
    """
    Toma una cotización o plantilla existente, extrae sus datos y los envía
    al formulario de creación como si fuera un documento nuevo.
    """
    plantilla = get_object_or_404(Cotizacion, pk=pk)
    
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
                'norma_manual': detalle.norma_manual,
                'metodo_manual': detalle.metodo_manual,
                'unidad_medida': detalle.unidad_medida,
                'cantidad': str(detalle.cantidad),
                'precio_unitario': str(detalle.precio_unitario),
                'total_detalle': str(detalle.total_detalle)
            })

    clientes = Cliente.objects.all().order_by('razon_social')
    servicios_queryset = Servicio.objects.all().select_related('norma', 'metodo')
    categorias_principales = CategoriaServicio.objects.all()
    subcategorias_list = Subcategoria.objects.all()
    trabajadores = TrabajadorProfile.objects.all().select_related('user')

    servicios_list = [{
        'pk': s.pk, 
        'nombre': s.nombre, 
        'unidad_base': s.unidad_base,
        'precio_base': str(s.precio_base),
        'norma_codigo': s.norma.codigo if s.norma else 'N/A',
        'metodo_codigo': s.metodo.codigo if s.metodo else 'N/A',
    } for s in servicios_queryset]

    context = {
        'cotizacion': plantilla,  
        'clientes': clientes,
        'servicios': servicios_queryset,
        'servicio_grupos': categorias_principales,
        'subcategorias': subcategorias_list,
        'servicios_con_detalles_json': json.dumps(servicios_list),
        'detalles_cotizacion_json': json.dumps(detalles_list), 
        'trabajadores': trabajadores,
        'es_clonacion': True, 
        'estados_choices': Cotizacion.ESTADO_CHOICES,
        'forma_pago_choices': Cotizacion.FORMA_PAGO_CHOICES,
    }
    
    return render(request, 'servicios/cotizaciones_form.html', context)

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

def generar_pdf_cotizacion(request, pk):
    cotizacion = get_object_or_404(
        Cotizacion.objects.prefetch_related('grupos__detalles_items__servicio')
                          .select_related('cliente', 'trabajador_responsable'),
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

    context = {
        'cotizacion': cotizacion,
        'grupos': cotizacion.grupos.all().order_by('orden'), # Clave para el ordenamiento
        'subtotal_final': subtotal,
        'igv_monto_final': igv_amount,
        'monto_total_final': monto_total,
        'igv_porcentaje': igv_porcentaje, 
        'jefe_laboratorio': jefe_laboratorio,
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
        return redirect('proyectos:lista_proyectos_pendientes')

    if request.method == 'POST':
        codigo_voucher = request.POST.get('codigo_voucher', '').strip()
        monto_pagado_str = request.POST.get('monto_pagado', '0').strip()
        imagen_voucher = request.FILES.get('imagen_voucher')
        documento_firmado_cliente = request.FILES.get('documento_firmado_cliente')
        
        try:
            monto_pagado = Decimal(monto_pagado_str.replace(',', ''))
        except (TypeError, InvalidOperation, ValueError):
            monto_pagado = Decimal('0.00')

        if not codigo_voucher or not imagen_voucher or not documento_firmado_cliente:
            return render(request, 'servicios/aprobar_cotizacion.html', {
                'cotizacion': cotizacion,
                'error': 'Todos los campos y archivos son obligatorios.',
                'codigo_voucher_value': codigo_voucher,
                'monto_pagado_value': monto_pagado_str,
            })

        try:
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
            
            Proyecto.objects.get_or_create(
                cotizacion=cotizacion,
                defaults={
                    'nombre_proyecto': nombre_proyecto,
                    'codigo_proyecto': codigo_proyecto, 
                    'cliente': cotizacion.cliente,
                    'estado': 'PENDIENTE',
                    'descripcion_proyecto': "Proyecto generado automáticamente.",
                    'monto_cotizacion': cotizacion.monto_total,
                    'codigo_voucher': voucher.codigo,
                    'numero_muestras': total_muestras,
                }
            )
            
            return redirect('proyectos:lista_proyectos_pendientes')
    
        except Exception as e:
            logger.error(f"Error en aprobación {pk}: {str(e)}", exc_info=True)
            return render(request, 'servicios/aprobar_cotizacion.html', {
                'cotizacion': cotizacion,
                'error': f'Ocurrió un error al procesar la aprobación: {str(e)}',
                'codigo_voucher_value': codigo_voucher,
                'monto_pagado_value': monto_pagado_str,
            })
    
    return render(request, 'servicios/aprobar_cotizacion.html', {'cotizacion': cotizacion})

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