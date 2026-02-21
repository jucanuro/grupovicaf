from django.views.generic import ListView
import datetime
import json
import io
from django.http import JsonResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from django.http import HttpResponse
from django.template.loader import get_template
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from .utils import enviar_whatsapp_pdf
from django.views.decorators.http import require_POST
from .models import Proyecto, TipoMuestra, RecepcionMuestra, MuestraDetalle, SolicitudEnsayo, DetalleSolicitudEnsayo, IncidenciaSolicitud
from servicios.models import Servicio, CotizacionDetalle, CategoriaServicio, Subcategoria, CotizacionGrupo,Cotizacion
from trabajadores.models import TrabajadorProfile


def get_date_or_none(date_string):
    return date_string if date_string and date_string.strip() else None

def generar_correlativo_lote():
    """Genera código tipo REC-2026-0001"""
    anio = datetime.datetime.now().year
    ultimo = RecepcionMuestraLote.objects.filter(numero_registro__icontains=f"-{anio}-").order_by('-id').first()
    numero = 1
    if ultimo:
        try:
            numero = int(ultimo.numero_registro.split('-')[-1]) + 1
        except (ValueError, IndexError): pass
    return f"REC-{anio}-{numero:04d}"

def generar_codigo_vicaf(servicio_obj):
    """Genera ID LAB tipo S-2026-001 basado en la inicial de la subcategoría"""
    prefijo = "X"
    if servicio_obj.subcategoria:
        prefijo = servicio_obj.subcategoria.nombre[0].upper()
    
    anio = datetime.datetime.now().year
    ultimo = MuestraItem.objects.filter(codigo_vicaf__startswith=f"{prefijo}-{anio}").order_by('-id').first()
    numero = 1
    if ultimo:
        try:
            numero = int(ultimo.codigo_vicaf.split('-')[-1]) + 1
        except (ValueError, IndexError): pass
    return f"{prefijo}-{anio}-{numero:03d}"


@login_required
def lista_proyectos_pendientes(request):
    """Panel principal de proyectos en curso"""
    proyectos_qs = Proyecto.objects.select_related('cliente', 'cotizacion').filter(
        ~Q(estado__in=['FINALIZADO', 'CANCELADO'])
    )

    search_query = request.GET.get('search', '')
    if search_query:
        proyectos_qs = proyectos_qs.filter(
            Q(nombre_proyecto__icontains=search_query) |
            Q(codigo_proyecto__icontains=search_query) |
            Q(cliente__razon_social__icontains=search_query)
        )
    
    proyectos_list = proyectos_qs.order_by('-creado_en')
    paginator = Paginator(proyectos_list, 10)
    proyectos_paginados = paginator.get_page(request.GET.get('page'))

    context = {
        'proyectos_pendientes': proyectos_paginados,
        'search_query': search_query,
        'titulo_lista': 'Panel de Control de Proyectos',
    }
    return render(request, 'proyectos/lista_proyectos_pendientes.html', context)

@require_POST
def crear_tipo_muestra_ajax(request):
    nombre = request.POST.get('nombre', '').strip()
    sigla = request.POST.get('sigla', '').upper().strip() 
    
    if not nombre or not sigla:
        return JsonResponse({
            'status': 'error', 
            'message': 'Nombre y Sigla son obligatorios.'
        }, status=400)
    
    try:
        tipo, created = TipoMuestra.objects.get_or_create(
            sigla=sigla, 
            defaults={'nombre': nombre}
        )
        
        return JsonResponse({
            'status': 'success',
            'id': tipo.pk,
            'nombre': tipo.nombre,
            'sigla': tipo.sigla,
            'nuevo': created
        })

    except IntegrityError:
        return JsonResponse({
            'status': 'error', 
            'message': f'La sigla "{sigla}" ya está registrada con otro nombre.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': 'Error interno del servidor.'
        }, status=500)
    
def gestionar_recepcion_muestra(request, proyecto_id):
    proyecto = get_object_or_404(
        Proyecto.objects.select_related('cotizacion__cliente'), 
        pk=proyecto_id
    )
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                fecha_str = request.POST.get('fecha_recepcion')
                hora_str = request.POST.get('hora_recepcion') or "00:00"
                
                if fecha_str:
                    fecha_final_str = f"{fecha_str} {hora_str}"
                   
                    fecha_final = fecha_final_str
                else:
                    fecha_final = timezone.now()

                recepcion = RecepcionMuestra.objects.create(
                    cotizacion=proyecto.cotizacion,
                    procedencia=request.POST.get('procedencia', '').upper(),
                    responsable_cliente=request.POST.get('responsable_entrega', '').upper(),
                    telefono=request.POST.get('telefono_entrega', ''),
                    fecha_recepcion=fecha_final,
                    fecha_muestreo=request.POST.get('fecha_muestreo') or None,
                    responsable_recepcion=request.user,
                )

                tipos_ids = request.POST.getlist('tipo_muestra_id[]')
                cantidades = request.POST.getlist('cantidad[]')
                unidades = request.POST.getlist('unidad[]')
                masas = request.POST.getlist('masa[]')
                descripciones = request.POST.getlist('descripcion[]')
                observaciones_list = request.POST.getlist('observaciones[]')

                muestras_a_crear = []
                for i in range(len(tipos_ids)):
                    if tipos_ids[i]:
                        try:
                            cant_val = int(float(cantidades[i])) if i < len(cantidades) and cantidades[i] else 1
                            masa_val = float(masas[i]) if i < len(masas) and masas[i] else 0.0
                        except ValueError:
                            cant_val = 1
                            masa_val = 0.0

                        muestra = MuestraDetalle(
                            recepcion=recepcion,
                            tipo_muestra_id=tipos_ids[i],
                            nro_item=i + 1, 
                            descripcion=descripciones[i][:255] if i < len(descripciones) else '',
                            masa_aprox=masa_val,
                            cantidad=cant_val,
                            unidad=unidades[i].upper() if i < len(unidades) and unidades[i] else 'UND',
                            observaciones=observaciones_list[i] if i < len(observaciones_list) else ''
                        )
                        muestras_a_crear.append(muestra)

                for m in muestras_a_crear:
                    m.save()

                messages.success(request, f"¡Éxito! Recepción #{recepcion.id} y {len(muestras_a_crear)} muestras registradas.")
                return redirect('proyectos:lista_muestras_recepcion', recepcion_id=recepcion.id)

        except Exception as e:
            print(f"Error Crítico: {e}")
            messages.error(request, f"Ocurrió un error al guardar: {str(e)}")

    tipos_qs = TipoMuestra.objects.all().order_by('nombre')
    tipos_muestra_json = json.dumps([
        {'id': t.id, 'nombre': t.nombre, 'prefijo': t.sigla} for t in tipos_qs
    ])

    context = {
        'proyecto': proyecto,
        'fecha_hoy': timezone.now().strftime('%Y-%m-%d'),
        'hora_ahora': timezone.now().strftime('%H:%M'),
        'tipos_muestra_json': tipos_muestra_json,
    }
    return render(request, 'proyectos/recepcion_form.html', context)

def lista_muestras_recepcion(request, recepcion_id):
    recepcion = get_object_or_404(
        RecepcionMuestra.objects.select_related('cotizacion__cliente', 'responsable_recepcion'), 
        pk=recepcion_id
    )
    
    proyecto_obj = Proyecto.objects.filter(cotizacion=recepcion.cotizacion).first()
    
    muestras = MuestraDetalle.objects.filter(recepcion=recepcion).select_related('tipo_muestra')
    
    return render(request, 'proyectos/muestras_list.html', {
        'recepcion': recepcion,
        'muestras': muestras,
        'proyecto': proyecto_obj  
    })
    
class RecepcionMuestraListView(ListView):
    model = RecepcionMuestra
    template_name = 'proyectos/lista_general_recepciones.html'
    context_object_name = 'recepciones'
    paginate_by = 20 

    def get_queryset(self):
        queryset = RecepcionMuestra.objects.select_related(
            'cotizacion__cliente', 
            'responsable_recepcion'
        ).prefetch_related('muestras').order_by('-fecha_recepcion')

        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(cotizacion__cliente__nombre__icontains=query) |
                Q(id__icontains=query) |
                Q(procedencia__icontains=query)
            )
        return queryset
    
def generar_pdf_recepcion(request, recepcion_id):
    recepcion = get_object_or_404(
        RecepcionMuestra.objects.select_related(
            'cotizacion__cliente', 
            'responsable_recepcion'
        ).prefetch_related('muestras__tipo_muestra'), 
        id=recepcion_id
    )
    
    proyecto = Proyecto.objects.filter(cotizacion=recepcion.cotizacion).first()

    context = {
        'recepcion': recepcion,
        'muestras': recepcion.muestras.all(),
        'proyecto': proyecto,
        'cliente': recepcion.cotizacion.cliente,
        'user': request.user,
    }

    html_string = render_to_string('proyectos/muestras_pdf.html', context)
    
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf_file = html.write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Cargo_Recepcion_{recepcion.id}.pdf"'
    
    return response

def generar_y_enviar_whatsapp(request, recepcion_id):
    recepcion = get_object_or_404(RecepcionMuestra, id=recepcion_id)
    muestras = recepcion.muestras.all()
    
    if hasattr(recepcion, 'cotizacion'):
        cliente = recepcion.cotizacion.cliente
    else:
        cliente = getattr(recepcion, 'cliente', None)

    template_path = 'proyectos/muestras_pdf.html' 
    
    try:
        html_string = render_to_string(template_path, {
            'recepcion': recepcion,
            'muestras': muestras,
            'cliente': cliente,
        })
        
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
        
        nombre_archivo = f"Recepcion_{recepcion.id}.pdf"
        ruta_archivo = os.path.join(settings.MEDIA_ROOT, 'pdfs', nombre_archivo)
        
        os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)
        
        with open(ruta_archivo, 'wb') as f:
            f.write(pdf_file)

        if cliente and cliente.telefono:
            url_publica_pdf = request.build_absolute_uri(settings.MEDIA_URL + 'pdfs/' + nombre_archivo)
            enviar_whatsapp_pdf(cliente.telefono, url_publica_pdf, recepcion.id)
            messages.success(request, "WhatsApp enviado con éxito.")
        else:
            messages.warning(request, "PDF generado, pero el cliente no tiene teléfono.")

    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
    
    return redirect('proyectos:lista_muestras_recepcion', recepcion_id=recepcion.id)



def gestionar_solicitud_ensayo(request, pk=None):
    if pk:
        solicitud = get_object_or_404(SolicitudEnsayo, pk=pk)
        detalles = solicitud.detalles.all()
    else:
        solicitud = None
        detalles = []

    if request.method == 'POST':
        codigo = request.POST.get('codigo_solicitud')
        recepcion_id = request.POST.get('recepcion')
        cotizacion_id = request.POST.get('cotizacion')
        f_solicitud = request.POST.get('fecha_solicitud')
        f_entrega_prog = request.POST.get('fecha_entrega_programada')
        elaborado_id = request.POST.get('elaborado_por')

        if solicitud:
            solicitud.codigo_solicitud = codigo
            solicitud.fecha_solicitud = f_solicitud
            solicitud.fecha_entrega_programada = f_entrega_prog
        else:
            solicitud = SolicitudEnsayo(
                codigo_solicitud=codigo,
                recepcion_id=recepcion_id,
                cotizacion_id=cotizacion_id,
                fecha_solicitud=f_solicitud,
                fecha_entrega_programada=f_entrega_prog,
                elaborado_por_id=elaborado_id
            )
        solicitud.save()

        muestras_ids = request.POST.getlist('muestra_id[]')
        servicios_ids = request.POST.getlist('servicio_id[]')
        descripciones = request.POST.getlist('descripcion[]')
        normas = request.POST.getlist('norma[]')
        metodos = request.POST.getlist('metodo[]')
        tecnicos_ids = request.POST.getlist('tecnico_id[]')
        entregas_det = request.POST.getlist('entrega_detalle[]')

        if pk:
            solicitud.detalles.all().delete()

        for i in range(len(muestras_ids)):
            if muestras_ids[i]: 
                DetalleSolicitudEnsayo.objects.create(
                    solicitud=solicitud,
                    muestra_id=muestras_ids[i],
                    servicio_cotizado_id=servicios_ids[i],
                    descripcion_ensayo=descripciones[i],
                    norma=normas[i],
                    metodo=metodos[i],
                    tecnico_asignado_id=tecnicos_ids[i] if tecnicos_ids[i] else None,
                    fecha_entrega_programada=entregas_det[i]
                )
        
        return redirect('proyectos:lista_solicitudes')

    context = {
        'solicitud': solicitud,
        'detalles': detalles,
        'recepciones': RecepcionMuestra.objects.all(),
        'cotizaciones': Cotizacion.objects.all(),
        'trabajadores': TrabajadorProfile.objects.all(),
        'servicios_items': CotizacionDetalle.objects.all(),
    }
    return render(request, 'proyectos/ensayos_form.html', context)


def lista_solicitudes(request):
    solicitudes = SolicitudEnsayo.objects.select_related('cotizacion__cliente', 'elaborado_por').all()
    
    q = request.GET.get('q')
    if q:
        solicitudes = solicitudes.filter(codigo_solicitud__icontains=q)
        
    return render(request, 'proyectos/ensayos_list.html', {
        'solicitudes': solicitudes
    })