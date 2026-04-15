from django.views.generic import ListView
from datetime import datetime
import json
import io
import logging
from django.db import IntegrityError
from django.http import JsonResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from django.http import HttpResponse
from django.template.loader import get_template
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Max
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from .utils import enviar_whatsapp_pdf
from django.views.decorators.http import require_POST
from django.db.models import Exists, OuterRef
from .models import Proyecto, TipoMuestra, RecepcionMuestra, MuestraDetalle,UnidadMedida, SolicitudEnsayo, DetalleSolicitudEnsayo, IncidenciaSolicitud, InformeFinal
from servicios.models import Servicio, CotizacionDetalle, CategoriaServicio, Subcategoria, CotizacionGrupo,Cotizacion
from trabajadores.models import TrabajadorProfile
import re
from urllib.parse import quote


logger = logging.getLogger(__name__)


def get_date_or_none(date_string):
    return date_string if date_string and date_string.strip() else None

def generar_correlativo_lote():
    anio = datetime.datetime.now().year
    ultimo = RecepcionMuestraLote.objects.filter(numero_registro__icontains=f"-{anio}-").order_by('-id').first()
    numero = 1
    if ultimo:
        try:
            numero = int(ultimo.numero_registro.split('-')[-1]) + 1
        except (ValueError, IndexError): pass
    return f"REC-{anio}-{numero:04d}"

def generar_codigo_vicaf(servicio_obj):
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

    for proyecto in proyectos_list:
        proyecto.etapa_operativa = 'PENDIENTE_MUESTRAS'
        proyecto.etapa_operativa_label = 'Pendiente de muestras'

        if proyecto.cotizacion:
            tiene_muestras = MuestraDetalle.objects.filter(
                recepcion__cotizacion=proyecto.cotizacion
            ).exists()

            if tiene_muestras:
                proyecto.etapa_operativa = 'MUESTRAS_REGISTRADAS'
                proyecto.etapa_operativa_label = 'Muestras registradas'

                solicitud = SolicitudEnsayo.objects.filter(
                    cotizacion=proyecto.cotizacion
                ).order_by('-id').first()

                if solicitud:
                    if solicitud.estado in ['pendiente', 'proceso']:
                        proyecto.etapa_operativa = 'ENSAYOS_EN_PROCESO'
                        proyecto.etapa_operativa_label = 'Ensayos en proceso'
                    elif solicitud.estado == 'finalizado':
                        informe = InformeFinal.objects.filter(solicitud=solicitud).first()
                        if informe:
                            proyecto.etapa_operativa = 'INFORME_EMITIDO'
                            proyecto.etapa_operativa_label = 'Informe emitido'
                        else:
                            proyecto.etapa_operativa = 'PENDIENTE_INFORME'
                            proyecto.etapa_operativa_label = 'Pendiente de informe'

    paginator = Paginator(proyectos_list, 10)
    proyectos_paginados = paginator.get_page(request.GET.get('page'))

    context = {
        'proyectos_pendientes': proyectos_paginados,
        'search_query': search_query,
        'titulo_lista': 'Panel de Control de Proyectos',
    }
    return render(request, 'proyectos/lista_proyectos_pendientes.html', context)

@require_POST
@login_required
def crear_tipo_muestra_ajax(request):
    try:
        nombre = request.POST.get('nombre', '').strip()
        sigla = request.POST.get('sigla', '').upper().strip() 
        
        if not nombre or len(nombre) < 2 or len(nombre) > 100:
            return JsonResponse({
                'status': 'error', 
                'message': 'Nombre debe tener entre 2 y 100 caracteres.'
            }, status=400)
        
        if not sigla or len(sigla) < 1 or len(sigla) > 10:
            return JsonResponse({
                'status': 'error', 
                'message': 'Sigla debe tener entre 1 y 10 caracteres.'
            }, status=400)

        import re
        if re.search(r'[<>]', nombre) or re.search(r'[<>]', sigla):
            logger.warning(f"Intento de XSS en crear_tipo_muestra_ajax por usuario {request.user.username}")
            return JsonResponse({
                'status': 'error', 
                'message': 'Caracteres no permitidos detectados.'
            }, status=400)
        
        tipo, created = TipoMuestra.objects.get_or_create(
            sigla=sigla, 
            defaults={'nombre': nombre}
        )
        
        if created:
            logger.info(f"Tipo de muestra creado exitosamente: {nombre} ({sigla}) por usuario {request.user.username}")
        else:
            logger.info(f"Tipo de muestra existente utilizado: {nombre} ({sigla}) por usuario {request.user.username}")
        
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
        logger.error(f"Error al crear tipo de muestra por usuario {request.user.username}: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': 'Error interno del servidor.'
        }, status=500)
    
def gestionar_recepcion_muestra(request, proyecto_id=None, pk=None):
    if pk and not proyecto_id:
        recepcion_temp = get_object_or_404(RecepcionMuestra, pk=pk)
        proyecto_obj = Proyecto.objects.filter(cotizacion=recepcion_temp.cotizacion).first()
        if not proyecto_obj:
            messages.error(request, 'No se encontró el proyecto asociado a esta recepción.')
            return redirect('proyectos:lista_proyectos_pendientes')
        proyecto_id = proyecto_obj.id

    if not proyecto_id:
        messages.error(request, 'Debe seleccionar un proyecto para crear una recepción.')
        return redirect('proyectos:lista_proyectos_pendientes')

    proyecto = get_object_or_404(
        Proyecto.objects.select_related('cotizacion__cliente'),
        pk=proyecto_id
    )

    recepcion = None
    is_editing = pk is not None
    if is_editing:
        recepcion = get_object_or_404(RecepcionMuestra, pk=pk, cotizacion=proyecto.cotizacion)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                if not is_editing:
                    fecha_str = request.POST.get('fecha_recepcion')
                    hora_str = request.POST.get('hora_recepcion') or "00:00"

                    if fecha_str:
                        fecha_final = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
                        fecha_final = timezone.make_aware(fecha_final, timezone.get_current_timezone())
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
                unidades_ids = request.POST.getlist('unidad_medida_id[]')
                masas = request.POST.getlist('masa[]')
                descripciones = request.POST.getlist('descripcion[]')
                observaciones_list = request.POST.getlist('observaciones[]')

                muestras_a_crear = []
                for i in range(len(tipos_ids)):
                    if tipos_ids[i]:
                        try:
                            cant_val = int(float(cantidades[i])) if i < len(cantidades) and cantidades[i] else 1
                        except ValueError:
                            cant_val = 1

                        try:
                            masa_val = Decimal(str(masas[i])) if i < len(masas) and masas[i] else Decimal('0.00')
                        except (InvalidOperation, ValueError):
                            masa_val = Decimal('0.00')

                        unidad_medida_id = None
                        if i < len(unidades_ids) and unidades_ids[i]:
                            unidad_medida_id = unidades_ids[i]

                        muestra = MuestraDetalle(
                            recepcion=recepcion,
                            tipo_muestra_id=tipos_ids[i],
                            nro_item=recepcion.muestras.count() + i + 1,  # Continuar numeración
                            descripcion=descripciones[i][:255] if i < len(descripciones) else '',
                            masa_aprox=masa_val,
                            cantidad=cant_val,
                            unidad_medida_id=unidad_medida_id,
                            observaciones=observaciones_list[i] if i < len(observaciones_list) else ''
                        )
                        muestras_a_crear.append(muestra)

                for m in muestras_a_crear:
                    m.save()

                action_text = "agregadas" if is_editing else "registradas"
                messages.success(
                    request,
                    f"¡Éxito! {len(muestras_a_crear)} muestras {action_text} a la recepción #{recepcion.id}."
                )
                return redirect('proyectos:lista_muestras_recepcion', recepcion_id=recepcion.id)

        except Exception as e:
            print(f"Error Crítico: {e}")
            messages.error(request, f"Ocurrió un error al guardar: {str(e)}")

    tipos_qs = TipoMuestra.objects.all().order_by('nombre')
    tipos_muestra_json = json.dumps([
        {'id': t.id, 'nombre': t.nombre, 'prefijo': t.sigla} for t in tipos_qs
    ])

    unidades_qs = UnidadMedida.objects.filter(activo=True).order_by('codigo')
    unidades_medida_json = json.dumps([
        {'id': u.id, 'codigo': u.codigo, 'nombre': u.nombre} for u in unidades_qs
    ])

    muestras_existentes = []
    if recepcion:
        for muestra in recepcion.muestras.select_related('tipo_muestra', 'unidad_medida').all():
            muestras_existentes.append({
                'tipo_muestra_id': muestra.tipo_muestra.id,
                'tipo_muestra_nombre': muestra.tipo_muestra.nombre,
                'cantidad': str(muestra.cantidad),
                'unidad_medida_id': muestra.unidad_medida.id if muestra.unidad_medida else '',
                'masa': str(muestra.masa_aprox),
                'descripcion': muestra.descripcion,
                'observaciones': muestra.observaciones or '',
                'codigo_laboratorio': muestra.codigo_laboratorio or ''
            })

    context = {
        'proyecto': proyecto,
        'recepcion': recepcion,  # Pasar la recepción si existe
        'fecha_hoy': timezone.now().strftime('%Y-%m-%d'),
        'hora_ahora': timezone.now().strftime('%H:%M'),
        'tipos_muestra_json': tipos_muestra_json,
        'unidades_medida_json': unidades_medida_json,
        'muestras_existentes_json': json.dumps(muestras_existentes),
        'is_editing': is_editing,
    }
    return render(request, 'proyectos/recepcion_form.html', context)

def lista_muestras_recepcion(request, recepcion_id):
    recepcion = get_object_or_404(
        RecepcionMuestra.objects.select_related('cotizacion__cliente', 'responsable_recepcion'),
        pk=recepcion_id
    )

    proyecto_obj = Proyecto.objects.filter(cotizacion=recepcion.cotizacion).first()
    muestras = MuestraDetalle.objects.filter(recepcion=recepcion).select_related('tipo_muestra')

    cliente = None
    telefono_whatsapp = ""

    if hasattr(recepcion, 'cotizacion') and recepcion.cotizacion:
        cliente = recepcion.cotizacion.cliente
    else:
        cliente = getattr(recepcion, 'cliente', None)

    if cliente:
        telefono_whatsapp = (
            getattr(cliente, 'telefono', '') or
            getattr(cliente, 'telefono_contacto', '') or
            getattr(cliente, 'celular_contacto', '') or
            ''
        )

    return render(request, 'proyectos/muestras_list.html', {
        'recepcion': recepcion,
        'muestras': muestras,
        'proyecto': proyecto_obj,
        'telefono_whatsapp': telefono_whatsapp,
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
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    pdf_file = html.write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Cargo_Recepcion_{recepcion.id}.pdf"'

    return response


def limpiar_numero_whatsapp(numero: str) -> str:
    if not numero:
        return ""
    return re.sub(r"\D", "", numero)


def limpiar_numero_whatsapp(numero: str) -> str:
    if not numero:
        return ""
    return re.sub(r"\D", "", numero)


@login_required
def generar_y_enviar_whatsapp(request, recepcion_id):
    try:
        recepcion = get_object_or_404(
            RecepcionMuestra.objects.select_related(
                'cotizacion__cliente',
                'responsable_recepcion'
            ),
            id=recepcion_id
        )

        if request.method != 'POST':
            return JsonResponse({
                'ok': False,
                'message': 'Método no permitido.'
            }, status=405)

        if hasattr(recepcion, 'cotizacion') and recepcion.cotizacion:
            cliente = recepcion.cotizacion.cliente
        else:
            cliente = getattr(recepcion, 'cliente', None)

        telefono_manual = request.POST.get('telefono', '').strip()

        if len(telefono_manual) > 20:
            return JsonResponse({
                'ok': False,
                'message': 'Número de teléfono no puede exceder 20 caracteres.'
            }, status=400)

        import re
        if re.search(r'[<>]', telefono_manual):
            logger.warning(f"Intento de XSS en generar_y_enviar_whatsapp por usuario {request.user.username}")
            return JsonResponse({
                'ok': False,
                'message': 'Caracteres no permitidos detectados.'
            }, status=400)

        telefono_cliente = ""
        if cliente:
            telefono_cliente = (
                getattr(cliente, 'telefono', '') or
                getattr(cliente, 'telefono_contacto', '') or
                getattr(cliente, 'celular_contacto', '') or
                ''
            )

        telefono_destino = limpiar_numero_whatsapp(telefono_manual or telefono_cliente)

        if not telefono_destino:
            return JsonResponse({
                'ok': False,
                'message': 'No se encontró un número válido de WhatsApp.'
            }, status=400)

        if len(telefono_destino) < 9:
            return JsonResponse({
                'ok': False,
                'message': 'Número de teléfono inválido.'
            }, status=400)

        pdf_url = request.build_absolute_uri(
            f"/proyectos/recepcion/{recepcion.id}/pdf/"
        )

        mensaje = (
            f"Estimado cliente, le compartimos el Cargo de Recepción de Muestras N° {recepcion.id:05d}.\n\n"
            f"Puede verlo o descargarlo aquí:\n{pdf_url}"
        )

        whatsapp_url = f"https://wa.me/{telefono_destino}?text={quote(mensaje)}"

        logger.info(f"WhatsApp generado para recepción {recepcion.id} por usuario {request.user.username}")

        return JsonResponse({
            'ok': True,
            'whatsapp_url': whatsapp_url
        })
    except Exception as e:
        logger.error(f"Error al generar WhatsApp para recepción {recepcion_id} por usuario {request.user.username}: {str(e)}")
        return JsonResponse({
            'ok': False,
            'message': 'Error interno del servidor.'
        }, status=500)
    
@login_required
def api_obtener_detalles_cotizacion(request, cotizacion_id):
    try:
        try:
            cotizacion_id = int(cotizacion_id)
            if cotizacion_id <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ID de cotización inválido.'}, status=400)

        cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_id)

        # Recepción activa de la cotización
        recepcion = RecepcionMuestra.objects.filter(
            cotizacion=cotizacion
        ).order_by('-id').first()

        solicitud_existente = None
        if recepcion:
            solicitud_existente = SolicitudEnsayo.objects.filter(
                recepcion=recepcion
            ).select_related('cotizacion', 'recepcion').first()

        # 1) Detalles ya asignados en ESTA solicitud
        detalles_asignados = []
        servicios_registrados_ids = set()

        if solicitud_existente:
            detalles_qs = solicitud_existente.detalles.select_related(
                'muestra',
                'servicio_cotizado__servicio',
                'tecnico_asignado'
            ).order_by('id')

            for d in detalles_qs:
                servicios_registrados_ids.add(d.servicio_cotizado_id)

                detalles_asignados.append({
                    'detalle_id': d.id,
                    'muestra_id': d.muestra_id,
                    'muestra_codigo': d.muestra.codigo_laboratorio if d.muestra else '',
                    'servicio_cotizado_id': d.servicio_cotizado_id,
                    'nombre_servicio': d.servicio_cotizado.servicio.nombre if d.servicio_cotizado and d.servicio_cotizado.servicio else "Servicio",
                    'norma': d.norma or '',
                    'metodo': d.metodo or '',
                    'tecnico_id': d.tecnico_asignado_id or '',
                    'tecnico_nombre': d.tecnico_asignado.nombre_completo if d.tecnico_asignado else '-- Sin Asignar --',
                    'fecha_entrega': d.fecha_entrega_programada.strftime('%Y-%m-%d') if d.fecha_entrega_programada else '',
                })

        # 2) Servicios pendientes de ESTA cotización, excluyendo los ya registrados
        detalles_cotizacion = CotizacionDetalle.objects.filter(
            grupo__cotizacion=cotizacion
        ).exclude(
            id__in=servicios_registrados_ids
        ).select_related('servicio').order_by('id')

        servicios_pendientes = []
        for item in detalles_cotizacion:
            norma = item.norma_manual or (item.servicio.norma if item.servicio else "")
            metodo = item.metodo_manual or (item.servicio.metodo if item.servicio else "")

            servicios_pendientes.append({
                'cotizacion_detalle_id': item.id,
                'servicio_id': item.servicio.id if item.servicio else None,
                'nombre_servicio': item.servicio.nombre if item.servicio else "Servicio Especial",
                'norma': str(norma),
                'metodo': str(metodo),
            })

        # 3) Muestras disponibles para esa cotización
        muestras = list(
            MuestraDetalle.objects.filter(
                recepcion__cotizacion=cotizacion
            ).order_by('codigo_laboratorio').values(
                'id', 'codigo_laboratorio', 'descripcion'
            )[:100]
        )

        logger.info(
            f"Estado actual de cotización {cotizacion_id} consultado por usuario {request.user.username}"
        )

        return JsonResponse({
            'solicitud_existente_id': solicitud_existente.id if solicitud_existente else None,
            'detalles_asignados': detalles_asignados,
            'servicios_pendientes': servicios_pendientes,
            'muestras': muestras,
            'bloquear_cotizacion': len(servicios_pendientes) == 0 and len(detalles_asignados) > 0,
        })

    except Exception as e:
        logger.error(
            f"Error al obtener detalles de cotización {cotizacion_id} por usuario {request.user.username}: {str(e)}"
        )
        return JsonResponse({'error': 'Error interno del servidor.'}, status=500)

@transaction.atomic
@login_required
def gestionar_solicitud_ensayo(request, pk=None):
    solicitud = get_object_or_404(SolicitudEnsayo, pk=pk) if pk else None

    if request.method == 'POST':
        try:
            perfil_trabajador = TrabajadorProfile.objects.filter(user=request.user).first()

            if not perfil_trabajador:
                messages.error(
                    request,
                    "Tu usuario no tiene un perfil de trabajador asociado. Contacta al administrador antes de registrar ensayos."
                )
                return redirect(request.path)

            cotizacion_id = request.POST.get('cotizacion')
            fecha_solicitud_raw = request.POST.get('fecha_solicitud')
            fecha_entrega_cabecera_raw = request.POST.get('fecha_entrega_programada')

            if not cotizacion_id:
                raise Exception("Debe seleccionar una Cotización.")

            fecha_solicitud = (
                datetime.strptime(fecha_solicitud_raw, "%Y-%m-%d").date()
                if fecha_solicitud_raw else timezone.now().date()
            )

            if not fecha_entrega_cabecera_raw:
                raise Exception("Debe indicar la fecha de entrega programada.")

            fecha_entrega_cabecera = datetime.strptime(
                fecha_entrega_cabecera_raw, "%Y-%m-%d"
            ).date()

            recepcion = RecepcionMuestra.objects.filter(
                cotizacion_id=cotizacion_id
            ).order_by('-id').first()

            if not recepcion:
                raise Exception("No existe una Recepción para esta Cotización.")

            with transaction.atomic():
                if not solicitud:
                    solicitud = SolicitudEnsayo.objects.filter(recepcion=recepcion).first()

                if solicitud:
                    solicitud.cotizacion_id = cotizacion_id
                    solicitud.recepcion = recepcion
                    solicitud.fecha_solicitud = fecha_solicitud
                    solicitud.fecha_entrega_programada = fecha_entrega_cabecera

                    if not solicitud.elaborado_por_id:
                        solicitud.elaborado_por = perfil_trabajador

                    solicitud.save()
                else:
                    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_id)
                    year_part = str(timezone.now().year)
                    cot_num = cotizacion.numero_oferta.split('-')[-1] if cotizacion.numero_oferta else '000'
                    prefix_sol = f'SOL-{cot_num}-{year_part}'

                    max_result = SolicitudEnsayo.objects.filter(
                        codigo_solicitud__startswith=f'{prefix_sol}-'
                    ).aggregate(Max('codigo_solicitud'))

                    last_num_sol = max_result.get('codigo_solicitud__max')
                    next_order_num = 1
                    if last_num_sol:
                        try:
                            next_order_num = int(last_num_sol.split('-')[-1]) + 1
                        except (IndexError, ValueError):
                            next_order_num = 1

                    codigo_solicitud = f'{prefix_sol}-{str(next_order_num).zfill(3)}'

                    solicitud = SolicitudEnsayo.objects.create(
                        codigo_solicitud=codigo_solicitud,
                        recepcion=recepcion,
                        cotizacion_id=cotizacion_id,
                        fecha_solicitud=fecha_solicitud,
                        fecha_entrega_programada=fecha_entrega_cabecera,
                        elaborado_por=perfil_trabajador,
                        estado='pendiente'
                    )

                muestras_ids = request.POST.getlist('muestra_id[]')
                servicios_ids = request.POST.getlist('servicio_id[]')
                normas = request.POST.getlist('norma[]')
                metodos = request.POST.getlist('metodo[]')
                tecnicos_ids = request.POST.getlist('tecnico_id[]')
                entregas_det = request.POST.getlist('entrega_detalle[]')

                ids_serv = [s for s in servicios_ids if s.strip()]
                serv_map = {
                    str(c.id): c
                    for c in CotizacionDetalle.objects.filter(
                        id__in=ids_serv,
                        grupo__cotizacion_id=cotizacion_id
                    ).select_related('servicio')
                }

                muestras_validas = set(
                    MuestraDetalle.objects.filter(
                        recepcion__cotizacion_id=cotizacion_id
                    ).values_list('id', flat=True)
                )

                servicios_ya_guardados = set(
                    solicitud.detalles.values_list('servicio_cotizado_id', flat=True)
                )

                ensayos_list = []
                omitidas = 0

                total_filas = max(
                    len(muestras_ids),
                    len(servicios_ids),
                    len(tecnicos_ids),
                    len(entregas_det)
                )

                for i in range(total_filas):
                    m_id = muestras_ids[i].strip() if i < len(muestras_ids) and muestras_ids[i] else ""
                    s_id = servicios_ids[i].strip() if i < len(servicios_ids) and servicios_ids[i] else ""
                    tecnico_id = tecnicos_ids[i].strip() if i < len(tecnicos_ids) and tecnicos_ids[i] else ""
                    fecha_entrega_det = entregas_det[i].strip() if i < len(entregas_det) and entregas_det[i] else ""

                    if not m_id and not s_id and not tecnico_id and not fecha_entrega_det:
                        continue

                    if not (m_id and s_id and tecnico_id and fecha_entrega_det):
                        omitidas += 1
                        continue

                    try:
                        m_id_int = int(m_id)
                        s_id_int = int(s_id)
                    except ValueError:
                        omitidas += 1
                        continue

                    if m_id_int not in muestras_validas:
                        omitidas += 1
                        continue

                    if s_id_int in servicios_ya_guardados:
                        continue

                    cot_det = serv_map.get(s_id)
                    if not cot_det:
                        omitidas += 1
                        continue

                    try:
                        fecha_entrega_det_obj = datetime.strptime(fecha_entrega_det, "%Y-%m-%d").date()
                    except ValueError:
                        omitidas += 1
                        continue

                    norma_val = normas[i].strip() if i < len(normas) and normas[i] else ""
                    metodo_val = metodos[i].strip() if i < len(metodos) and metodos[i] else ""

                    ensayos_list.append(
                        DetalleSolicitudEnsayo(
                            solicitud=solicitud,
                            muestra_id=m_id_int,
                            servicio_cotizado_id=s_id_int,
                            descripcion_ensayo=cot_det.servicio.nombre if cot_det.servicio else "Ensayo",
                            norma=norma_val,
                            metodo=metodo_val,
                            tecnico_asignado_id=tecnico_id,
                            fecha_entrega_programada=fecha_entrega_det_obj
                        )
                    )
                    servicios_ya_guardados.add(s_id_int)

                if ensayos_list:
                    DetalleSolicitudEnsayo.objects.bulk_create(ensayos_list)

                inc_detalles = request.POST.getlist('incidencia_detalle[]')
                inc_fechas = request.POST.getlist('incidencia_fecha[]')
                inc_clientes = request.POST.getlist('incidencia_cliente[]')
                inc_responsables = request.POST.getlist('incidencia_responsable_id[]')
                inc_autorizados = request.POST.getlist('incidencia_autorizado[]')

                incidencias_existentes = set(
                    solicitud.incidencias.values_list('detalle_incidencia', 'representante_cliente')
                )

                incidencias_list = []
                for j in range(len(inc_detalles)):
                    texto = inc_detalles[j].strip() if j < len(inc_detalles) and inc_detalles[j] else ""
                    if not texto:
                        continue

                    is_auth = j < len(inc_autorizados) and inc_autorizados[j].lower() == 'true'
                    responsable_id = inc_responsables[j].strip() if j < len(inc_responsables) and inc_responsables[j] else None
                    representante_cliente = inc_clientes[j] if j < len(inc_clientes) else ""

                    try:
                        fecha_ocurrencia = datetime.strptime(inc_fechas[j], "%Y-%m-%dT%H:%M") if j < len(inc_fechas) and inc_fechas[j] else timezone.now()
                    except ValueError:
                        fecha_ocurrencia = timezone.now()

                    key_inc = (texto, representante_cliente)
                    if key_inc in incidencias_existentes:
                        continue

                    nueva_inc = IncidenciaSolicitud(
                        solicitud=solicitud,
                        detalle_incidencia=texto,
                        fecha_ocurrencia=fecha_ocurrencia,
                        representante_cliente=representante_cliente,
                        representante_laboratorio_id=responsable_id,
                        esta_autorizada=is_auth
                    )

                    if is_auth:
                        nueva_inc.autorizado_por = perfil_trabajador
                        nueva_inc.fecha_autorizacion = timezone.now()

                    incidencias_list.append(nueva_inc)

                if incidencias_list:
                    IncidenciaSolicitud.objects.bulk_create(incidencias_list)

            if omitidas:
                messages.warning(
                    request,
                    f"Se guardó el avance. {omitidas} fila(s) incompletas no se registraron."
                )
            else:
                messages.success(request, f"Solicitud {solicitud.codigo_solicitud} guardada con éxito.")

            return redirect('proyectos:lista_solicitudes')

        except Exception as e:
            print("ERROR EN gestionar_solicitud_ensayo:", repr(e))
            messages.error(request, f"Error: {str(e)}")
            return redirect(request.path)

    proyecto_id = request.GET.get('proyecto')
    cotizacion_preseleccionada = None

    if proyecto_id and not solicitud:
        proyecto = Proyecto.objects.filter(pk=proyecto_id).select_related('cotizacion').first()
        if proyecto and proyecto.cotizacion:
            cotizacion_preseleccionada = proyecto.cotizacion

    if request.method == 'GET' and not solicitud:
        cotizacion_id = request.GET.get('cotizacion')
        if cotizacion_id:
            recepcion_existente = RecepcionMuestra.objects.filter(
                cotizacion_id=cotizacion_id
            ).order_by('-id').first()

            if recepcion_existente:
                solicitud_existente = SolicitudEnsayo.objects.filter(
                    recepcion=recepcion_existente
                ).first()

                if solicitud_existente:
                    solicitud = solicitud_existente

    cotizaciones_disponibles_ids = []

    cotizaciones_qs = (
        Cotizacion.objects
        .filter(
            estado='Aceptada',
            recepciones__isnull=False
        )
        .select_related('cliente')
        .distinct()
        .order_by('-fecha_creacion')
    )

    for cot in cotizaciones_qs:
        total_servicios = CotizacionDetalle.objects.filter(
            grupo__cotizacion=cot
        ).count()

        recepcion = RecepcionMuestra.objects.filter(
            cotizacion=cot
        ).order_by('-id').first()

        solicitud_existente = None
        if recepcion:
            solicitud_existente = SolicitudEnsayo.objects.filter(
                recepcion=recepcion
            ).first()

        servicios_registrados = 0
        if solicitud_existente:
            servicios_registrados = solicitud_existente.detalles.values(
                'servicio_cotizado_id'
            ).distinct().count()

        if not solicitud_existente or servicios_registrados < total_servicios:
            cotizaciones_disponibles_ids.append(cot.id)

    if solicitud and solicitud.cotizacion_id and solicitud.cotizacion_id not in cotizaciones_disponibles_ids:
        cotizaciones_disponibles_ids.append(solicitud.cotizacion_id)

    if cotizacion_preseleccionada and cotizacion_preseleccionada.pk not in cotizaciones_disponibles_ids:
        cotizaciones_disponibles_ids.append(cotizacion_preseleccionada.pk)

    cotizaciones = Cotizacion.objects.filter(
        pk__in=cotizaciones_disponibles_ids
    ).select_related('cliente').order_by('-fecha_creacion')

    cotizacion_activa = solicitud.cotizacion if solicitud else cotizacion_preseleccionada

    servicios_registrados_ids = (
        solicitud.detalles.values_list('servicio_cotizado_id', flat=True)
        if solicitud else []
    )

    servicios_items = CotizacionDetalle.objects.filter(
        grupo__cotizacion=cotizacion_activa
    ).exclude(
        id__in=servicios_registrados_ids
    ).select_related('servicio') if cotizacion_activa else CotizacionDetalle.objects.none()

    muestras_disponibles = MuestraDetalle.objects.filter(
        recepcion__cotizacion=cotizacion_activa
    ).select_related('tipo_muestra', 'unidad_medida') if cotizacion_activa else MuestraDetalle.objects.none()

    dias_plazo = ""

    if solicitud and solicitud.fecha_solicitud and solicitud.fecha_entrega_programada:
        try:
            dias_plazo = (solicitud.fecha_entrega_programada - solicitud.fecha_solicitud).days
        except Exception:
            dias_plazo = ""

    context = {
        'solicitud': solicitud,
        'detalles': solicitud.detalles.select_related(
            'muestra', 'servicio_cotizado__servicio', 'tecnico_asignado'
        ).all() if solicitud else [],
        'incidencias': solicitud.incidencias.all() if solicitud else [],
        'cotizaciones': cotizaciones,
        'cotizacion_preseleccionada': cotizacion_activa,
        'trabajadores': TrabajadorProfile.objects.all(),
        'muestras_disponibles': muestras_disponibles,
        'servicios_items': servicios_items,
        'dias_plazo': dias_plazo,
    }
    return render(request, 'proyectos/ensayos_form.html', context)

@require_POST
def cambiar_estado_solicitud(request, pk, nuevo_estado):
    solicitud = get_object_or_404(SolicitudEnsayo, pk=pk)

    estados_validos = ['pendiente', 'proceso', 'finalizado']
    if nuevo_estado not in estados_validos:
        messages.error(request, "Estado no válido.")
        return redirect('proyectos:lista_solicitudes')

    solicitud.estado = nuevo_estado

    if nuevo_estado == 'finalizado':
        if not solicitud.fecha_entrega_real:
            solicitud.fecha_entrega_real = timezone.now().date()

    solicitud.save()

    if nuevo_estado == 'finalizado':
        messages.success(request, f"La solicitud {solicitud.codigo_solicitud} fue finalizada. Ahora registra el informe final.")
        return redirect('proyectos:gestionar_informe', solicitud_id=solicitud.pk)

    messages.success(request, f"La solicitud {solicitud.codigo_solicitud} cambió a estado {nuevo_estado.upper()}.")
    return redirect('proyectos:lista_solicitudes')

def lista_solicitudes(request):
    solicitudes = SolicitudEnsayo.objects.prefetch_related('detalles').select_related(
        'cotizacion__cliente', 
        'elaborado_por'
    ).all().order_by('-fecha_solicitud', '-id')
    
    q = request.GET.get('q', '').strip()
    if q:
        solicitudes = solicitudes.filter(
            Q(codigo_solicitud__icontains=q) | 
            Q(cotizacion__cliente__razon_social__icontains=q) |
            Q(cotizacion__numero_oferta__icontains=q)
        ).distinct()
        
    return render(request, 'proyectos/ensayos_list.html', {
        'solicitudes': solicitudes,
        'q': q
    })
    
def generar_pdf_ensayo(request, solicitud_id):
    solicitud = get_object_or_404(
        SolicitudEnsayo.objects.select_related('cotizacion__cliente'), 
        id=solicitud_id
    )
    
    from .models import Proyecto 
    proyecto = Proyecto.objects.filter(cotizacion=solicitud.cotizacion).first()

    detalles = solicitud.detalles.select_related(
        'muestra', 
        'tecnico_asignado__user'  
    ).all()

    context = {
        'solicitud': solicitud,
        'proyecto': proyecto,
        'detalles': detalles,
        'user': request.user,
    }

    html_string = render_to_string('proyectos/ensayos_pdf.html', context)
    
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf_file = html.write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"Solicitud_Ensayo_{solicitud.id}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response

def lista_informes_finales(request):
    informes = InformeFinal.objects.all().order_by('-fecha_emision')
    return render(request, 'proyectos/informes_list.html', {
        'informes': informes
    })

def gestionar_informe_final(request, solicitud_id=None):
    solicitud = None
    informe = None
    
    status_filter = request.GET.get('status')
    query = request.GET.get('q')

    pendientes = SolicitudEnsayo.objects.filter(
        estado='finalizado', 
        informe_final__isnull=True
    ).select_related('cotizacion__cliente')

    if solicitud_id:
        solicitud = get_object_or_404(SolicitudEnsayo, id=solicitud_id)
        informe = InformeFinal.objects.filter(solicitud=solicitud).first()
    
    trabajadores = TrabajadorProfile.objects.all()

    if request.method == 'POST':
        archivo = request.FILES.get('archivo_pdf')
        responsable_id = request.POST.get('responsable_firma')
        sid = solicitud_id or request.POST.get('solicitud_id')

        if not sid:
            messages.error(request, "Debe seleccionar un ensayo válido.")
            return redirect('proyectos:lista_informes')

        solicitud_actual = get_object_or_404(SolicitudEnsayo, id=sid)
        informe_actual = InformeFinal.objects.filter(solicitud=solicitud_actual).first()

        try:
            if informe_actual:
                informe_actual.responsable_firma_id = responsable_id
                if archivo:
                    informe_actual.archivo_pdf = archivo
                    informe_actual.save() 
                    informe_actual.estampar_qr_en_pdf() 
                else:
                    informe_actual.save()
                messages.success(request, f"Informe {informe_actual.codigo_informe} actualizado.")
            else:
                if not archivo:
                    messages.error(request, "El archivo PDF es obligatorio para nuevos informes.")
                    return render(request, 'proyectos/informes_form.html', locals())
                
                nuevo = InformeFinal.objects.create(
                    solicitud=solicitud_actual,
                    archivo_pdf=archivo,
                    responsable_firma_id=responsable_id
                )
                nuevo.estampar_qr_en_pdf()
                messages.success(request, f"Informe {nuevo.codigo_informe} generado con éxito.")

            return redirect('proyectos:lista_informes')

        except Exception as e:
            print(f"DEBUG ERROR: {e}") 
            messages.error(request, f"Error al procesar el informe: {e}")

    return render(request, 'proyectos/informes_form.html', {
        'solicitud': solicitud,
        'informe': informe,
        'pendientes': pendientes,
        'trabajadores': trabajadores,
        'status_filter': status_filter, 
        'query': query                  
    })
  
def descargar_pdf_informe(request, informe_id):
    informe = get_object_or_404(InformeFinal, id=informe_id)
    
    if not informe.archivo_pdf:
        raise Http404("El archivo no está disponible.")

    informe.descargas_count += 1
    informe.save(update_fields=['descargas_count'])

    return FileResponse(
        informe.archivo_pdf.open(), 
        as_attachment=True, 
        filename=f"Informe_{informe.codigo_informe}.pdf"
    )

def validar_informe_publico(request, slug_validacion):
    informe = get_object_or_404(InformeFinal, slug_validacion=slug_validacion)
    
    return render(request, 'proyectos/validar_publico.html', {
        'informe': informe
    })





