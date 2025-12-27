from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from django.views.generic import ListView
from django.urls import reverse_lazy
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
import json
from django.http import HttpRequest
import os
from django.db import IntegrityError
from django.http import HttpResponse
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.db import IntegrityError
from django.utils import timezone
from .models import Proyecto,DocumentoFinal, SolicitudEnsayo,DetalleEnsayo, Muestra,TipoEnsayo, AsignacionTipoEnsayo, ReporteIncidencia, TipoMuestra, Laboratorio, ResultadoEnsayo, ResultadoEnsayoValor, EnsayoParametro
from clientes.models import Cliente as Cliente 
from servicios.models import Cotizacion,CotizacionDetalle, Norma, Metodo
from trabajadores.models import TrabajadorProfile
from django.contrib import messages
from decimal import Decimal, InvalidOperation
import datetime
from django.conf import settings
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.db.models import Prefetch
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.contrib import messages

try:
    from .models import ResultadoEnsayo 
except ImportError:
    class ResultadoEnsayo:
        DoesNotExist = Exception 
        pass 

@login_required
def lista_proyectos_pendientes(request): 
    proyectos_qs = Proyecto.objects.all().order_by('-creado_en')
    proyectos_frescos = list(proyectos_qs) 

    context = {
        'proyectos_pendientes': proyectos_frescos,
        'titulo_lista': 'Todos los Proyectos para Gestión', 
    }
    
    return render(request, 'proyectos/lista_proyectos_pendientes.html', context)

def get_date_or_none(date_string):
    """Convierte una cadena de fecha a formato YYYY-MM-DD o None si está vacía."""
    return date_string if date_string else None

def get_fk_object(model_class, pk_value):
    """
    Intenta obtener un objeto de la base de datos usando su clave primaria (PK).
    Devuelve None si el pk_value es None/vacío o si el objeto no se encuentra.
    """
    if not pk_value:
        return None
    try:
        return model_class.objects.filter(pk=pk_value).first()
    except Exception:
        return None

class MuestraCreateUpdateView(TemplateView):
    template_name = 'proyectos/gestion_dashboard_muestras.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proyecto_pk = self.kwargs.get('pk')
        
        proyecto = get_object_or_404(Proyecto, pk=proyecto_pk)
        
        context['proyecto'] = proyecto
        muestra_pk = self.kwargs.get('muestra_pk')
        
        muestra = None
        is_update = False
        form_data = {}

        if 'form_data' in kwargs:
            form_data = kwargs.get('form_data', {})
        elif muestra_pk:
            try:
                muestra = get_object_or_404(Muestra, pk=muestra_pk, proyecto=proyecto)
                is_update = True
                
                form_data = {
                    'muestra_pk_to_edit': str(muestra.pk), 
                    'tipo_muestra': str(muestra.tipo_muestra.pk) if muestra.tipo_muestra else '',
                    'id_lab': str(muestra.id_lab.pk) if muestra.id_lab else '',
                    'estado': muestra.estado,
                    
                    'descripcion_muestra': muestra.descripcion_muestra,
                    'estado_fisico_recepcion': muestra.estado_fisico_recepcion,
                    'masa_aprox_kg': str(muestra.masa_aprox_kg) if muestra.masa_aprox_kg else '',
                    'ubicacion_almacenamiento': muestra.ubicacion_almacenamiento,
                    'ubicacion_gps': muestra.ubicacion_gps,
                    'notas_recepcion': muestra.notas_recepcion,
                    
                    'fecha_toma_muestra': muestra.fecha_toma_muestra.strftime('%Y-%m-%d') if muestra.fecha_toma_muestra else '',
                    'fecha_recepcion': muestra.fecha_recepcion.strftime('%Y-%m-%d') if muestra.fecha_recepcion else '',
                    'fecha_fabricacion': muestra.fecha_fabricacion.strftime('%Y-%m-%d') if muestra.fecha_fabricacion else '',
                    'fecha_ensayo_rotura': muestra.fecha_ensayo_rotura.strftime('%Y-%m-%d') if muestra.fecha_ensayo_rotura else '',
                    
                    'tomada_por': str(muestra.tomada_por.pk) if muestra.tomada_por else '',
                    'recepcionado_por': str(muestra.recepcionado_por.pk) if muestra.recepcionado_por else '',
                    'tecnico_responsable_muestra': str(muestra.tecnico_responsable_muestra.pk) if muestra.tecnico_responsable_muestra else '',
                }
                
                context['title'] = f"✏️ Editando Muestra: {muestra.codigo_muestra}"
                
            except Exception:
                context['title'] = "➕ Registrar Nueva Muestra"
                is_update = False
        else:
            context['title'] = "➕ Registrar Nueva Muestra"

        context['form_data'] = form_data
        context['is_update'] = is_update
        
        # Carga de datos estadísticos y FKs (permanecen igual)
        lista_muestras = Muestra.objects.filter(proyecto=proyecto).order_by('pk')
        context['lista_muestras'] = lista_muestras
        context['muestras_registradas'] = lista_muestras.count()
        context['muestras_totales'] = proyecto.numero_muestras
        context['muestras_pendientes'] = context['muestras_totales'] - context['muestras_registradas']
        
        try:
            context['laboratorios'] = Laboratorio.objects.all()
            context['tipos_muestra'] = TipoMuestra.objects.all().order_by('nombre')
            context['trabajadores'] = TrabajadorProfile.objects.all().order_by('nombre') 
        except Exception:
            context['laboratorios'] = []
            context['tipos_muestra'] = []
            context['trabajadores'] = []

        context['estados_muestra'] = Muestra.ESTADOS_MUESTRA
            
        return context
    
    def post(self, request, *args, **kwargs):
        proyecto_pk = kwargs.get('pk')
        proyecto = get_object_or_404(Proyecto, pk=proyecto_pk)
        
        muestra_pk_to_edit = request.POST.get('muestra_pk_to_edit')
        is_update = bool(muestra_pk_to_edit)

        # 1. Determinar instancia y validación de límite (solo para CREACIÓN)
        if is_update:
            instance = get_object_or_404(Muestra, pk=muestra_pk_to_edit, proyecto=proyecto)
            mensaje_exito = f"Muestra {instance.codigo_muestra} actualizada exitosamente."
        else:
            muestras_actuales = Muestra.objects.filter(proyecto=proyecto).count()
            if muestras_actuales >= proyecto.numero_muestras:
                mensaje = f"Límite alcanzado: Ya se registraron {muestras_actuales} muestras. El límite es {proyecto.numero_muestras}."
                messages.warning(request, mensaje)
                return redirect(reverse('proyectos:gestion_muestras_proyecto', kwargs={'pk': proyecto_pk}))

            instance = Muestra(proyecto=proyecto)
            mensaje_exito = "Muestra registrada exitosamente."

        try:
            
            id_lab_pk = request.POST.get('id_lab')
            tipo_muestra_pk = request.POST.get('tipo_muestra')

            instance.id_lab = get_fk_object(Laboratorio, id_lab_pk)
            instance.tipo_muestra = get_fk_object(TipoMuestra, tipo_muestra_pk)
            
            if not instance.id_lab or not instance.tipo_muestra:
                raise ValueError("Faltan campos obligatorios: Laboratorio y Tipo de Muestra.")

            instance.descripcion_muestra = request.POST.get('descripcion_muestra', '').strip()
            instance.estado_fisico_recepcion = request.POST.get('estado_fisico_recepcion', '').strip()
            instance.ubicacion_almacenamiento = request.POST.get('ubicacion_almacenamiento', '').strip()
            instance.ubicacion_gps = request.POST.get('ubicacion_gps', '').strip()
            instance.estado = request.POST.get('estado', 'RECIBIDA') # Por si es creación
            instance.notas_recepcion = request.POST.get('notas_recepcion', '').strip()

            masa_str = request.POST.get('masa_aprox_kg', '').strip()
            instance.masa_aprox_kg = Decimal(masa_str) if masa_str else None

            instance.fecha_toma_muestra = request.POST.get('fecha_toma_muestra', '').strip() or None
            instance.fecha_fabricacion = request.POST.get('fecha_fabricacion', '').strip() or None
            instance.fecha_ensayo_rotura = request.POST.get('fecha_ensayo_rotura', '').strip() or None
            
            fecha_recepcion_str = request.POST.get('fecha_recepcion', '').strip()
            if not is_update and not fecha_recepcion_str:
                 instance.fecha_recepcion = timezone.now().date() 
            elif fecha_recepcion_str:
                 instance.fecha_recepcion = fecha_recepcion_str

            instance.tomada_por = get_fk_object(TrabajadorProfile, request.POST.get('tomada_por'))
            instance.recepcionado_por = get_fk_object(TrabajadorProfile, request.POST.get('recepcionado_por'))
            instance.tecnico_responsable_muestra = get_fk_object(TrabajadorProfile, request.POST.get('tecnico_responsable_muestra'))

            instance.full_clean()
            instance.save()
            
            messages.success(request, mensaje_exito)
            
            return redirect(reverse('proyectos:gestion_muestras_proyecto', kwargs={'pk': proyecto_pk}))

        except (ValueError, ValidationError) as e:
            error_message = f"Error de validación: {str(e)}"
            messages.error(request, error_message) 
            
            form_data = request.POST.dict()
            
            if is_update:
                return redirect(reverse('proyectos:gestion_muestras_proyecto', kwargs={'pk': proyecto_pk, 'muestra_pk': muestra_pk_to_edit}))
            
            return self.render_to_response(self.get_context_data(form_data=form_data, pk=proyecto_pk))
            
        except Exception as e:
            error_message = f"Error inesperado al guardar: {str(e)}"
            messages.error(request, error_message)
            return redirect(reverse('proyectos:gestion_muestras_proyecto', kwargs={'pk': proyecto_pk}))
        
class ProyectoMuestraGestionView(TemplateView):
    template_name = 'proyectos/gestion_dashboard_muestras.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proyecto_pk = self.kwargs.get('pk')
        
        proyecto = get_object_or_404(Proyecto, pk=proyecto_pk)
        
        muestra_pk = self.kwargs.get('muestra_pk') 
        form_data = kwargs.get('form_data', {})
        is_update = False
        
        if muestra_pk and not form_data:
            try:
                muestra = get_object_or_404(Muestra, pk=muestra_pk, proyecto=proyecto)
                is_update = True
                
                form_data = {
                    'muestra_pk_to_edit': str(muestra.pk),
                    'tipo_muestra': str(muestra.tipo_muestra.pk) if muestra.tipo_muestra else '',
                    'id_lab': str(muestra.id_lab.pk) if muestra.id_lab else '',
                    'estado': muestra.estado,
                    
                    'descripcion_muestra': muestra.descripcion_muestra or '',
                    'estado_fisico_recepcion': muestra.estado_fisico_recepcion or '',
                    
                    'masa_aprox_kg': str(muestra.masa_aprox_kg) if muestra.masa_aprox_kg is not None else '',
                    
                    'ubicacion_almacenamiento': muestra.ubicacion_almacenamiento or '',
                    'ubicacion_gps': muestra.ubicacion_gps or '',
                    'notas_recepcion': muestra.notas_recepcion or '',
                    
                    'fecha_toma_muestra': muestra.fecha_toma_muestra.strftime('%Y-%m-%d') if isinstance(muestra.fecha_toma_muestra, datetime.date) else '',
                    'fecha_recepcion': muestra.fecha_recepcion.strftime('%Y-%m-%d') if isinstance(muestra.fecha_recepcion, datetime.date) else '',
                    'fecha_fabricacion': muestra.fecha_fabricacion.strftime('%Y-%m-%d') if isinstance(muestra.fecha_fabricacion, datetime.date) else '',
                    'fecha_ensayo_rotura': muestra.fecha_ensayo_rotura.strftime('%Y-%m-%d') if isinstance(muestra.fecha_ensayo_rotura, datetime.date) else '',
                    
                    'tomada_por': str(muestra.tomada_por.pk) if muestra.tomada_por else '',
                    'recepcionado_por': str(muestra.recepcionado_por.pk) if muestra.recepcionado_por else '',
                    'tecnico_responsable_muestra': str(muestra.tecnico_responsable_muestra.pk) if muestra.tecnico_responsable_muestra else '',
                }
                context['title'] = f"✏️ Editando Muestra: {muestra.codigo_muestra or muestra.pk}"
                
            except Muestra.DoesNotExist:
                messages.warning(self.request, "La muestra solicitada no existe o no pertenece a este proyecto.")
                is_update = False
            
        if not is_update:
            context['title'] = "➕ Registrar Nueva Muestra"

        context['form_data'] = form_data
        context['is_update'] = is_update
        
        muestras_registradas = Muestra.objects.filter(proyecto=proyecto).count()
        muestras_totales = proyecto.numero_muestras
        muestras_pendientes = max(0, muestras_totales - muestras_registradas)

        context['proyecto'] = proyecto
        context['muestras_registradas'] = muestras_registradas
        context['muestras_totales'] = muestras_totales
        context['muestras_pendientes'] = muestras_pendientes
        
        try:
            context['laboratorios'] = Laboratorio.objects.all()
            context['tipos_muestra'] = TipoMuestra.objects.all()
            context['trabajadores'] = TrabajadorProfile.objects.all()
        except NameError:
             pass 

        context['estados_muestra'] = Muestra.ESTADOS_MUESTRA
        context['lista_muestras'] = Muestra.objects.filter(proyecto=proyecto).order_by('-fecha_recepcion')

        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        proyecto_pk = kwargs.get('pk')
        proyecto = get_object_or_404(Proyecto, pk=proyecto_pk)
        
        muestra_pk_to_edit = request.POST.get('muestra_pk_to_edit')
        is_update = bool(muestra_pk_to_edit)
        
        if is_update:
            instance = get_object_or_404(Muestra, pk=muestra_pk_to_edit, proyecto=proyecto)
            mensaje_exito = f"Muestra {instance.codigo_muestra or instance.pk} actualizada exitosamente."
        else:
            muestras_actuales = Muestra.objects.filter(proyecto=proyecto).count()
            if muestras_actuales >= proyecto.numero_muestras:
                messages.error(request, f"Límite de muestras alcanzado ({muestras_actuales}/{proyecto.numero_muestras}).")
                return redirect(reverse('proyectos:gestion_muestras_proyecto', kwargs={'pk': proyecto_pk}))

            instance = Muestra(proyecto=proyecto)
            mensaje_exito = "Muestra registrada exitosamente."
            
        try:
            instance.id_lab = get_fk_object(Laboratorio, request.POST.get('id_lab'))
            instance.tipo_muestra = get_fk_object(TipoMuestra, request.POST.get('tipo_muestra'))
            
            if not instance.id_lab or not instance.tipo_muestra:
                 raise ValidationError('El Laboratorio y el Tipo de Muestra son obligatorios.')
            
            instance.descripcion_muestra = request.POST.get('descripcion_muestra', '').strip()
            instance.estado = request.POST.get('estado')
            instance.estado_fisico_recepcion = request.POST.get('estado_fisico_recepcion', '').strip()
            instance.ubicacion_almacenamiento = request.POST.get('ubicacion_almacenamiento', '').strip()
            instance.ubicacion_gps = request.POST.get('ubicacion_gps', '').strip()
            instance.notas_recepcion = request.POST.get('notas_recepcion', '').strip()

            masa_str = request.POST.get('masa_aprox_kg', '').strip()

            if masa_str:
                masa_str = masa_str.replace(',', '.') 
                try:
                    instance.masa_aprox_kg = Decimal(masa_str)
                except Exception:
                    raise ValidationError("La masa debe ser un número válido, ej: 20, 20.5, 20.00.")
            else:
                instance.masa_aprox_kg = None
            
            instance.fecha_toma_muestra = request.POST.get('fecha_toma_muestra', '') or None
            instance.fecha_recepcion = request.POST.get('fecha_recepcion', '') or None
            instance.fecha_fabricacion = request.POST.get('fecha_fabricacion', '') or None
            instance.fecha_ensayo_rotura = request.POST.get('fecha_ensayo_rotura', '') or None
            
            instance.tomada_por = get_fk_object(TrabajadorProfile, request.POST.get('tomada_por'))
            instance.recepcionado_por = get_fk_object(TrabajadorProfile, request.POST.get('recepcionado_por'))
            instance.tecnico_responsable_muestra = get_fk_object(TrabajadorProfile, request.POST.get('tecnico_responsable_muestra'))

            instance.full_clean()
            instance.save()
            
            proyecto = Proyecto.objects.get(pk=proyecto.pk)
            
            proyecto.actualizar_estado_por_muestreo()
            
            
            messages.success(request, mensaje_exito)
            
            return redirect(reverse('proyectos:gestion_muestras_proyecto', kwargs={'pk': proyecto_pk}))

        
        except ValidationError as e:
            error_message = f"Error de Validación: {e.message_dict if hasattr(e, 'message_dict') else e.messages}"
            messages.error(request, error_message)
            
            form_data = request.POST.dict()
            
            if is_update:
                return redirect(reverse('proyectos:gestion_muestras_proyecto', 
                                        kwargs={'pk': proyecto_pk, 'muestra_pk': muestra_pk_to_edit}))
            
            return self.render_to_response(self.get_context_data(form_data=form_data, pk=proyecto_pk))

        except Exception as e:
            error_message = f"Error inesperado al guardar: {str(e)}"
            messages.error(request, error_message)
            
            return redirect(reverse('proyectos:gestion_muestras_proyecto', kwargs={'pk': proyecto_pk}))

@method_decorator(login_required, name='dispatch')
class ListaSolicitudesEnsayoView(ListView):
    model = SolicitudEnsayo
    template_name = 'listar_solicitudes_ensayo.html' 
    context_object_name = 'solicitudes'
    muestra_contexto = None

    def get_queryset(self):
        # Esta línea DEBE tener 8 espacios (o 2 niveles de indentación) desde el borde
        queryset = SolicitudEnsayo.objects.select_related('muestra').prefetch_related(
            'detalles_ensayo__asignaciones__tecnico_asignado__user',
            'detalles_ensayo__metodo'
        )
        
        muestra_pk = self.kwargs.get('muestra_pk')
        
        # El nombre del campo para ordenar (asegúrate que exista en SolicitudEnsayo)
        CAMPO_ORDEN = 'creado_en' 

        if muestra_pk:
            self.muestra_contexto = get_object_or_404(Muestra, pk=muestra_pk)
            return queryset.filter(muestra=self.muestra_contexto).order_by(f'-{CAMPO_ORDEN}')
        else:
            self.muestra_contexto = None
            return queryset.all().order_by(f'-{CAMPO_ORDEN}')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregamos la muestra al contexto (será None si es listado general)
        context['muestra'] = self.muestra_contexto 
        
        # Opcional: Útil para mostrar títulos diferentes en la plantilla
        context['es_listado_general'] = self.muestra_contexto is None 
        
        return context
           
@method_decorator(login_required, name='dispatch')
class GestionSolicitudEnsayoView(View):
    template_name = 'proyectos/solicitud_ensayo_gestion.html'

    def get_object_context(self, muestra_pk, solicitud_pk=None):
        muestra = get_object_or_404(Muestra, pk=muestra_pk)
        proyecto = muestra.proyecto
        
        solicitud = None
        detalles_existentes = DetalleEnsayo.objects.none()
        is_new = True

        if solicitud_pk:
            try:
                solicitud = SolicitudEnsayo.objects.get(pk=solicitud_pk, muestra=muestra)
                detalles_existentes = DetalleEnsayo.objects.filter(solicitud=solicitud).prefetch_related(
                    'norma',
                    'metodo',
                    'detalle_cotizacion',
                    'asignaciones__tecnico_asignado',
                    'asignaciones__tipo_ensayo',
                )
                is_new = False
            except SolicitudEnsayo.DoesNotExist:
                pass 
        
        tecnicos_serializados = list(
            TrabajadorProfile.objects.filter(role='TECNICO')
            .order_by('nombre_completo')
            .values('pk', 'nombre_completo')
        )
        tecnicos_final = [
            {'id': t['pk'], 'nombre_completo': t['nombre_completo']}
            for t in tecnicos_serializados
        ]
        
        normas = list(Norma.objects.all().values('id', 'nombre', 'codigo'))
        metodos = list(Metodo.objects.all().values('id', 'nombre', 'codigo'))
        tipos_ensayo = list(TipoEnsayo.objects.all().values('id', 'nombre', 'codigo_interno'))

        detalles_cotizacion = CotizacionDetalle.objects.filter(cotizacion=proyecto.cotizacion)
        context_cotizacion_details = list(detalles_cotizacion.values(
            'pk', 
            'descripcion_especifica', 
            'precio_unitario'
        ))
        
        solicitud_ya_detallada = solicitud and solicitud.estado != 'ASIGNADA'

        context = {
            'solicitud': solicitud,
            'muestra': muestra,
            'proyecto': proyecto,
            'tecnicos': tecnicos_final, 
            'normas': normas,
            'metodos': metodos,
            'tipos_ensayo': tipos_ensayo,
            'detalles_existentes': detalles_existentes,
            'detalles_cotizacion_json': context_cotizacion_details,
            'is_new': is_new,
            'solicitud_ya_detallada': solicitud_ya_detallada,
        }
        return context

    def get(self, request, muestra_pk, solicitud_pk=None):
        context = self.get_object_context(muestra_pk, solicitud_pk)
        return render(request, self.template_name, context)
    
    
    @transaction.atomic
    def post(self, request, muestra_pk, solicitud_pk=None): 
        muestra = get_object_or_404(Muestra, pk=muestra_pk)
        
        data = request.POST
        detalles_json = data.get('detalles_ensayo_json')
        
        try:
            detalles_data = json.loads(detalles_json)
        except (TypeError, json.JSONDecodeError):
            return JsonResponse({'success': False, 'message': 'Datos de detalles inválidos (JSON).'}, status=400)

        
        is_new = False
        if solicitud_pk:
            try:
                solicitud = SolicitudEnsayo.objects.get(pk=solicitud_pk, muestra=muestra)
            except SolicitudEnsayo.DoesNotExist:
                 return JsonResponse({'success': False, 'message': 'Solicitud de Ensayo no encontrada.'}, status=404)
        else:
            try:
                solicitud = muestra.solicitud_ensayo
            except SolicitudEnsayo.DoesNotExist:
                solicitud = SolicitudEnsayo(muestra=muestra, estado='ASIGNADA') 
                is_new = True

        trabajador_profile = getattr(request.user, 'trabajadorprofile', None)
        
        solicitud.generada_por_id = data.get('generada_por_id') or (trabajador_profile.pk if trabajador_profile else None)
        solicitud.fecha_entrega_programada = data.get('fecha_entrega_programada')
        
        if is_new:
            proyecto_codigo = getattr(muestra.proyecto, 'codigo_proyecto', 'PROYECTO')
            count = SolicitudEnsayo.objects.filter(muestra__proyecto=muestra.proyecto).count() + 1
            solicitud.codigo_solicitud = f"SEC-{proyecto_codigo}-{muestra.pk}-{count}"
            
        try:
            solicitud.full_clean()
            solicitud.save()
        except ValidationError as e:
            return JsonResponse({'success': False, 'message': f'Error de validación en la Solicitud: {e.message_dict}'}, status=400)

        
        detalles_ids_recibidos = [d.get('detalle_pk') for d in detalles_data if d.get('detalle_pk')]
        
        DetalleEnsayo.objects.filter(solicitud=solicitud).exclude(pk__in=detalles_ids_recibidos).delete()
        
        for detalle_data in detalles_data:
            detalle_pk = detalle_data.get('detalle_pk')
            
            if detalle_pk:
                detalle_ensayo = DetalleEnsayo.objects.get(pk=detalle_pk, solicitud=solicitud)
            else:
                detalle_ensayo = DetalleEnsayo(solicitud=solicitud)
            
            detalle_ensayo.tipo_ensayo_descripcion = detalle_data.get('descripcion')
            detalle_ensayo.fecha_limite_ejecucion = detalle_data.get('fecha_limite')
            detalle_ensayo.norma_id = detalle_data.get('norma_id') or None
            detalle_ensayo.metodo_id = detalle_data.get('metodo_id') or None
            detalle_ensayo.detalle_cotizacion_id = detalle_data.get('detalle_cotizacion_id') or None
            detalle_ensayo.observaciones_detalle = detalle_data.get('observaciones_detalle')
            detalle_ensayo.estado_detalle = detalle_data.get('estado_detalle', 'PENDIENTE')
            
            try:
                detalle_ensayo.full_clean()
                detalle_ensayo.save()
            except ValidationError as e:
                return JsonResponse({'success': False, 'message': f'Error de validación en detalle {detalle_ensayo.pk or "nuevo"}: {e.message_dict}'}, status=400)
            
            
            tecnicos_asignados_data = detalle_data.get('asignaciones', [])
            AsignacionTipoEnsayo.objects.filter(detalle=detalle_ensayo).delete() 
            
            asignaciones_a_crear = []
            for asignacion in tecnicos_asignados_data:
                tipo_ensayo_id = asignacion.get('tipo_ensayo_id')
                tecnico_id = asignacion.get('tecnico_id')
                
                if tipo_ensayo_id and tecnico_id:
                    asignaciones_a_crear.append(AsignacionTipoEnsayo(
                        detalle=detalle_ensayo,
                        tipo_ensayo_id=tipo_ensayo_id,
                        tecnico_asignado_id=tecnico_id
                    ))
            
            if asignaciones_a_crear:
                AsignacionTipoEnsayo.objects.bulk_create(asignaciones_a_crear)
        
        
        if hasattr(muestra.proyecto, 'actualizar_estado_por_muestreo'):
            muestra.proyecto.actualizar_estado_por_muestreo() 
        
        # --- Lógica de Redirección (Solución al "se queda pegado") ---
        response_data = {
            'success': True, 
            'solicitud_id': solicitud.pk, 
            'message': 'Solicitud y detalles guardados con éxito.'
        }
        
        if is_new:
            response_data['redirect_url'] = reverse('proyectos:lista_solicitudes_ensayo', kwargs={'muestra_pk': muestra_pk})
        else:
            response_data['redirect_url'] = reverse('proyectos:gestion_solicitud_ensayo_editar', kwargs={'muestra_pk': muestra_pk, 'solicitud_pk': solicitud.pk})

        return JsonResponse(response_data)
    
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

def header_footer_callback_solicitud(canvas, doc):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    from reportlab.lib.units import cm

    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    
    header_text = "Código: VCF-LAB-FOR-068 | Fecha: 10/11/2023 | Versión: 02"
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
  
def generar_pdf_solicitud_ensayo(request, pk):
    
    solicitud = get_object_or_404(SolicitudEnsayo.objects.all(), pk=pk) 
    
    jefe_laboratorio = None
    try:
        jefe_laboratorio = TrabajadorProfile.objects.select_related('user').get(user__username='raquel') 
    except (TrabajadorProfile.DoesNotExist, TrabajadorProfile.MultipleObjectsReturned):
        pass
    
    context = {
        'solicitud': solicitud,
        'items_ensayo': solicitud.detalles_ensayo.all(), 
        'jefe_laboratorio': jefe_laboratorio,
        'fecha_actual': timezone.now().date(),
    }

    template = get_template('solicitud_ensayo_pdf.html') 
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')

    nombre_archivo = f"VCF-LAB-FOR-068_SOLICITUD_{solicitud.codigo_solicitud or solicitud.pk}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"' 

    pisa_status = pisa.CreatePDF(
        html, 
        dest=response, 
        link_callback=link_callback 
    )

    if pisa_status.err:
        return HttpResponse('Tuvimos errores al generar el PDF de la Solicitud de Ensayo.', status=500)
    
    return response
  
@login_required
def listar_resultado_ensayo(request):
    """Lista todos los resultados de ensayos registrados con optimización de consultas."""
    resultados = ResultadoEnsayo.objects.select_related('tecnico_ejecutor').all()

    return render(request, 'listar_resultado_ensayo.html', {'resultados': resultados})
    

@login_required
@transaction.atomic
def registrar_resultado_ensayo(request):
    detalle_id = request.GET.get('detalle_id') or request.POST.get('detalle_ensayo_id')
    detalle = get_object_or_404(DetalleEnsayo, pk=detalle_id)
    
    # Obtenemos el tipo de ensayo de la relación ManyToMany (el primero asignado)
    tipo_ensayo_obj = detalle.tipos_ensayo.all().first()
    
    # Intentamos recuperar un resultado previo para edición
    resultado = ResultadoEnsayo.objects.filter(
        detalle_ensayo=detalle, 
        tipo_ensayo=tipo_ensayo_obj
    ).first()

    if request.method == 'POST':
        # 1. Registro/Actualización de la Cabecera (Modelo ResultadoEnsayo)
        if not resultado:
            resultado = ResultadoEnsayo(
                detalle_ensayo=detalle,
                tipo_ensayo=tipo_ensayo_obj,
                tecnico_ejecutor=getattr(request.user, 'trabajador_profile', None),
                estado='BORRADOR'
            )
        
        # Heredar o actualizar Norma y Método del modelo de Detalle o del POST
        resultado.norma_aplicada = detalle.norma
        resultado.metodo_aplicado = detalle.metodo
        resultado.fecha_inicio_ensayo = request.POST.get('fecha_inicio_ensayo')
        resultado.fecha_fin_ensayo = request.POST.get('fecha_fin_ensayo') or None
        resultado.es_reensayo = 'es_reensayo' in request.POST
        resultado.observaciones_tecnicas = request.POST.get('observaciones_tecnicas')
        
        resultado.save()

        # 2. Registro de Valores (Modelo ResultadoEnsayoValor)
        parametros = EnsayoParametro.objects.filter(tipo_ensayo=tipo_ensayo_obj)
        for param in parametros:
            valor_raw = request.POST.get(f'valor_p_{param.id}')
            cumple = request.POST.get(f'cumple_p_{param.id}') == 'on'
            
            if valor_raw is not None and valor_raw != "":
                val_obj, _ = ResultadoEnsayoValor.objects.get_or_create(
                    resultado=resultado, 
                    parametro=param
                )
                if param.es_numerico:
                    val_obj.valor_numerico = float(valor_raw.replace(',', '.'))
                else:
                    val_obj.valor_texto = valor_raw
                val_obj.cumple = cumple
                val_obj.save()

        messages.success(request, f"Resultado de {tipo_ensayo_obj.nombre} guardado.")
        return redirect('/proyectos/resultados/')

    # Preparación de datos para la interfaz
    parametros_qs = EnsayoParametro.objects.filter(tipo_ensayo=tipo_ensayo_obj)
    data_final = []
    for p in parametros_qs:
        valor_existente = ResultadoEnsayoValor.objects.filter(resultado=resultado, parametro=p).first() if resultado else None
        data_final.append({
            'meta': p,
            'valor': valor_existente.valor_numerico if (valor_existente and p.es_numerico) else (valor_existente.valor_texto if valor_existente else ""),
            'cumple': valor_existente.cumple if valor_existente else False
        })

    return render(request, 'registrar_resultado_ensayo.html', {
        'detalle': detalle,
        'resultado': resultado,
        'tipo_ensayo': tipo_ensayo_obj,
        'parametros_data': data_final,
        'today': timezone.now().date()
    })
    
def gestionar_informes(request):
    if request.method == "POST":
        proyecto_id = request.POST.get('proyecto_id')
        titulo = request.POST.get('titulo', 'Informe Técnico Final')
        archivo = request.FILES.get('archivo_pdf')
        publicar = request.POST.get('publicar') == 'on'

        if proyecto_id and archivo:
            proyecto = get_object_or_404(Proyecto, id=proyecto_id)
            
            DocumentoFinal.objects.update_or_create(
                proyecto=proyecto,
                defaults={
                    'titulo': titulo,
                    'archivo_pdf': archivo,
                    'publicado': publicar
                }
            )
            messages.success(request, f"Informe de {proyecto.codigo_proyecto} guardado con éxito.")
            # REDIRECCIÓN A LA LISTA
            return redirect('proyectos:lista_informes_finales') 
        
        messages.error(request, "Error: Datos incompletos.")
        return redirect('proyectos:gestionar_informes')

    # GET: Solo necesitamos los proyectos disponibles para crear nuevos
    proyectos_sin_informe = Proyecto.objects.filter(documento_final__isnull=True)
    return render(request, 'gestionar_informes.html', {
        'proyectos_disponibles': proyectos_sin_informe,
    })
    
def lista_informes_finales(request):
    informes = DocumentoFinal.objects.all().select_related(
        'proyecto__cliente', 
        'proyecto__cotizacion'
    ).order_by('-fecha_emision')
    
    return render(request, 'lista_informes.html', {
        'informes': informes
    })