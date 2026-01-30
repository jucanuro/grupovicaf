import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from .models import Proyecto, RecepcionMuestraLote, MuestraItem
from servicios.models import Servicio, CotizacionDetalle, CategoriaServicio, Subcategoria


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

@login_required
def registrar_recepcion_lote(request, proyecto_id):
    """
    Vista Robusta: Gestiona la recepción de muestras vinculando 
    automáticamente datos de servicios, normas y métodos.
    """
    proyecto = get_object_or_404(Proyecto.objects.select_related('cliente', 'cotizacion'), pk=proyecto_id)
    
    if request.method == 'POST':
        servicios_ids = request.POST.getlist('servicio_id[]')
        cantidades = request.POST.getlist('cantidad[]')
        unidades = request.POST.getlist('unidad[]')
        descripciones = request.POST.getlist('descripcion[]')
        masas = request.POST.getlist('masa[]')
        codigos_cli = request.POST.getlist('codigo_cliente[]')
        es_adicional_list = request.POST.getlist('es_adicional[]')
        observaciones = request.POST.getlist('observaciones[]')

        try:
            with transaction.atomic():
                lote = RecepcionMuestraLote.objects.create(
                    proyecto=proyecto,
                    numero_registro=generar_correlativo_lote(), 
                    responsable_entrega=request.POST.get('responsable_entrega'),
                    telefono_entrega=request.POST.get('telefono_entrega'),
                    fecha_recepcion=request.POST.get('fecha_recepcion'),
                    hora_recepcion=request.POST.get('hora_recepcion'),
                    fecha_muestreo=get_date_or_none(request.POST.get('fecha_muestreo')),
                    recepcionado_por=request.user.trabajador_profile
                )

                for i in range(len(servicios_ids)):
                    if not servicios_ids[i]: continue
                    
                    servicio = Servicio.objects.select_related('norma', 'metodo').get(pk=servicios_ids[i])
                    
                    MuestraItem.objects.create(
                        lote=lote,
                        servicio=servicio,
                        categoria=getattr(servicio, 'categoria', None),
                        subcategoria=getattr(servicio, 'subcategoria', None),
                        cantidad=cantidades[i],
                        unidad=unidades[i],
                        descripcion=descripciones[i],
                        masa_aproximada=masas[i],
                        codigo_cliente=codigos_cli[i],
                        observaciones=observaciones[i] if i < len(observaciones) else '',
                        es_adicional=(es_adicional_list[i].lower() == 'true'),
                        codigo_vicaf=generar_codigo_vicaf(servicio) # Tu función de generación de códigos
                    )
                
                proyecto.actualizar_estado_por_muestreo()

                messages.success(request, f"Recepción {lote.numero_registro} procesada con éxito.")
                return redirect('proyectos:lista_proyectos_pendientes')

        except Exception as e:
            messages.error(request, f"Fallo crítico en el registro: {str(e)}")

    detalles_cotizacion = CotizacionDetalle.objects.filter(
        grupo__cotizacion=proyecto.cotizacion
    ).select_related('servicio', 'servicio__norma', 'servicio__metodo')

    servicios_catalogo = Servicio.objects.all().select_related('norma', 'metodo')

    context = {
        'proyecto': proyecto,
        'detalles_cotizacion': detalles_cotizacion,
        'servicios_catalogo': servicios_catalogo,
        'fecha_hoy': timezone.now().date().isoformat(),
        'hora_ahora': timezone.now().time().strftime("%H:%M"),
    }
    return render(request, 'proyectos/form_recepcion_muestras.html', context)