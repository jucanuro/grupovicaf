
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
import json
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.db import IntegrityError
from django.utils import timezone
from .models import Proyecto, SolicitudEnsayo,DetalleEnsayo, Muestra,TipoEnsayo, AsignacionTipoEnsayo, ReporteIncidencia, TipoMuestra, Laboratorio
from clientes.models import Cliente as Cliente 
from servicios.models import Cotizacion,CotizacionDetalle, Norma, Metodo
from trabajadores.models import TrabajadorProfile
from django.contrib import messages
from decimal import Decimal, InvalidOperation
import datetime
from django.urls import reverse

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
    
    # Asume que aquí deberías tener los modelos importados:
    # Muestra, Proyecto, Laboratorio, TipoMuestra, TrabajadorProfile, Muestra.ESTADOS_MUESTRA

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proyecto_pk = self.kwargs.get('pk')
        
        proyecto = get_object_or_404(Proyecto, pk=proyecto_pk)
        
        context['proyecto'] = proyecto
        
        # 1. Intentar obtener el PK de la muestra de la URL para EDICIÓN
        #    Asume que la URL es: /proyectos/<int:pk>/muestras/<int:muestra_pk>/
        muestra_pk = self.kwargs.get('muestra_pk')
        
        muestra = None
        is_update = False
        form_data = {}

        if 'form_data' in kwargs:
            # Prioridad 1: Datos que fallaron en el POST
            form_data = kwargs.get('form_data', {})
        elif muestra_pk:
            try:
                # Prioridad 2: Cargar datos de la muestra para editar
                muestra = get_object_or_404(Muestra, pk=muestra_pk, proyecto=proyecto)
                is_update = True
                
                form_data = {
                    'muestra_pk_to_edit': str(muestra.pk), # PK de la muestra para el POST (Update)
                    'tipo_muestra': str(muestra.tipo_muestra.pk) if muestra.tipo_muestra else '',
                    'id_lab': str(muestra.id_lab.pk) if muestra.id_lab else '',
                    'estado': muestra.estado,
                    
                    'descripcion_muestra': muestra.descripcion_muestra,
                    'estado_fisico_recepcion': muestra.estado_fisico_recepcion,
                    'masa_aprox_kg': str(muestra.masa_aprox_kg) if muestra.masa_aprox_kg else '',
                    'ubicacion_almacenamiento': muestra.ubicacion_almacenamiento,
                    'ubicacion_gps': muestra.ubicacion_gps,
                    'notas_recepcion': muestra.notas_recepcion,
                    
                    # Formateo de fechas a 'YYYY-MM-DD' para HTML input type="date"
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
                # Si la muestra no se encuentra o hay error de carga, volvemos a modo Creación
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