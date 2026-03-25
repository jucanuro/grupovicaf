from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta
from django.utils import timezone
from datetime import datetime, timedelta
import datetime
from django.db.models import Q
from clientes.models import Cliente
from proyectos.models import Proyecto, RecepcionMuestra,MuestraDetalle, SolicitudEnsayo,DetalleSolicitudEnsayo,IncidenciaSolicitud, InformeFinal
from servicios.models import Cotizacion

class CoreLoginView(LoginView):
    template_name = 'core/login.html' 
    next_page = reverse_lazy('dashboard') 
    
    def form_invalid(self, form):
        messages.error(self.request, 'Usuario o contraseña incorrectos. Intente de nuevo.')
        return super().form_invalid(form)

@login_required
def dashboard_view(request):
    total_clientes = Cliente.objects.count()

    total_cotizaciones = Cotizacion.objects.count()
    total_cotizaciones_pendientes = Cotizacion.objects.filter(estado='Pendiente').count()
    total_cotizaciones_aceptadas = Cotizacion.objects.filter(estado='Aceptada').count()

    total_proyectos = Proyecto.objects.count()
    total_proyectos_pendiente = Proyecto.objects.filter(estado='PENDIENTE').count()
    total_proyectos_en_curso = Proyecto.objects.filter(estado='EN_CURSO').count()
    total_proyectos_muestras_asignadas = Proyecto.objects.filter(estado='MUESTRAS_ASIGNADAS').count()
    total_proyectos_muestras_validadas = Proyecto.objects.filter(estado='MUESTRAS_VALIDADAS').count()
    total_proyectos_finalizado = Proyecto.objects.filter(estado='FINALIZADO').count()
    total_proyectos_cancelado = Proyecto.objects.filter(estado='CANCELADO').count()

    total_recepciones = RecepcionMuestra.objects.count()
    total_muestras = MuestraDetalle.objects.count()

    total_solicitudes = SolicitudEnsayo.objects.count()
    total_ensayos = DetalleSolicitudEnsayo.objects.count()
    total_ensayos_pendiente = SolicitudEnsayo.objects.filter(estado='pendiente').count()
    total_ensayos_proceso = SolicitudEnsayo.objects.filter(estado='proceso').count()
    total_ensayos_finalizado = SolicitudEnsayo.objects.filter(estado='finalizado').count()

    total_incidencias = IncidenciaSolicitud.objects.count()
    total_incidencias_autorizadas = IncidenciaSolicitud.objects.filter(esta_autorizada=True).count()
    total_incidencias_pendientes = IncidenciaSolicitud.objects.filter(esta_autorizada=False).count()

    total_informes = InformeFinal.objects.count()
    total_informes_pendientes_envio = InformeFinal.objects.filter(estado_envio='pendiente').count()
    total_informes_enviados = InformeFinal.objects.filter(estado_envio='enviado').count()

    proyectos_con_muestras = Proyecto.objects.filter(
        cotizacion__recepciones__muestras__isnull=False
    ).distinct().count()

    proyectos_con_solicitud = Proyecto.objects.filter(
        cotizacion__solicitudes_ensayo__isnull=False
    ).distinct().count()

    proyectos_con_informe = Proyecto.objects.filter(
        cotizacion__solicitudes_ensayo__informe_final__isnull=False
    ).distinct().count()

    proyectos_sin_muestras = total_proyectos - proyectos_con_muestras
    proyectos_sin_solicitud = total_proyectos - proyectos_con_solicitud
    proyectos_sin_informe = total_proyectos - proyectos_con_informe

    solicitudes_vencidas = SolicitudEnsayo.objects.filter(
        estado__in=['pendiente', 'proceso'],
        fecha_entrega_programada__lt=timezone.now().date()
    ).count()

    detalles_vencidos = DetalleSolicitudEnsayo.objects.filter(
        fecha_entrega_real__isnull=True,
        fecha_entrega_programada__lt=timezone.now().date()
    ).count()

    efectividad = 0
    p_aceptadas = 0
    p_pendientes = 0
    o_pendientes = 0

    if total_cotizaciones > 0:
        efectividad = round((total_cotizaciones_aceptadas / total_cotizaciones) * 100)
        p_aceptadas = (total_cotizaciones_aceptadas / total_cotizaciones) * 100
        p_pendientes = (total_cotizaciones_pendientes / total_cotizaciones) * 100
        o_pendientes = -p_aceptadas

    p_e_finalizado = 0
    p_e_proceso = 0
    p_e_pendiente = 0
    o_e_proceso = 0
    o_e_pendiente = 0

    if total_solicitudes > 0:
        p_e_finalizado = (total_ensayos_finalizado / total_solicitudes) * 100
        p_e_proceso = (total_ensayos_proceso / total_solicitudes) * 100
        p_e_pendiente = (total_ensayos_pendiente / total_solicitudes) * 100

        o_e_proceso = -p_e_finalizado
        o_e_pendiente = -(p_e_finalizado + p_e_proceso)

    p_pr_pendiente = 0
    p_pr_en_curso = 0
    p_pr_muestras_asignadas = 0
    p_pr_muestras_validadas = 0
    p_pr_finalizado = 0
    p_pr_cancelado = 0

    o_pr_en_curso = 0
    o_pr_muestras_asignadas = 0
    o_pr_muestras_validadas = 0
    o_pr_finalizado = 0
    o_pr_cancelado = 0

    if total_proyectos > 0:
        p_pr_pendiente = (total_proyectos_pendiente / total_proyectos) * 100
        p_pr_en_curso = (total_proyectos_en_curso / total_proyectos) * 100
        p_pr_muestras_asignadas = (total_proyectos_muestras_asignadas / total_proyectos) * 100
        p_pr_muestras_validadas = (total_proyectos_muestras_validadas / total_proyectos) * 100
        p_pr_finalizado = (total_proyectos_finalizado / total_proyectos) * 100
        p_pr_cancelado = (total_proyectos_cancelado / total_proyectos) * 100

        o_pr_en_curso = -p_pr_pendiente
        o_pr_muestras_asignadas = -(p_pr_pendiente + p_pr_en_curso)
        o_pr_muestras_validadas = -(p_pr_pendiente + p_pr_en_curso + p_pr_muestras_asignadas)
        o_pr_finalizado = -(p_pr_pendiente + p_pr_en_curso + p_pr_muestras_asignadas + p_pr_muestras_validadas)
        o_pr_cancelado = -(p_pr_pendiente + p_pr_en_curso + p_pr_muestras_asignadas + p_pr_muestras_validadas + p_pr_finalizado)

    p_proyectos_con_muestras = (proyectos_con_muestras / total_proyectos * 100) if total_proyectos > 0 else 0
    p_proyectos_con_solicitud = (proyectos_con_solicitud / total_proyectos * 100) if total_proyectos > 0 else 0
    p_proyectos_con_informe = (proyectos_con_informe / total_proyectos * 100) if total_proyectos > 0 else 0

    context = {
        "total_clientes": total_clientes,

        "total_cotizaciones": total_cotizaciones,
        "total_cotizaciones_pendientes": total_cotizaciones_pendientes,
        "total_cotizaciones_aceptadas": total_cotizaciones_aceptadas,
        "efectividad": efectividad,
        "p_aceptadas": p_aceptadas,
        "p_pendientes": p_pendientes,
        "o_pendientes": o_pendientes,

        "total_proyectos": total_proyectos,
        "total_proyectos_pendiente": total_proyectos_pendiente,
        "total_proyectos_en_curso": total_proyectos_en_curso,
        "total_proyectos_muestras_asignadas": total_proyectos_muestras_asignadas,
        "total_proyectos_muestras_validadas": total_proyectos_muestras_validadas,
        "total_proyectos_finalizado": total_proyectos_finalizado,
        "total_proyectos_cancelado": total_proyectos_cancelado,

        "p_pr_pendiente": p_pr_pendiente,
        "p_pr_en_curso": p_pr_en_curso,
        "p_pr_muestras_asignadas": p_pr_muestras_asignadas,
        "p_pr_muestras_validadas": p_pr_muestras_validadas,
        "p_pr_finalizado": p_pr_finalizado,
        "p_pr_cancelado": p_pr_cancelado,

        "o_pr_en_curso": o_pr_en_curso,
        "o_pr_muestras_asignadas": o_pr_muestras_asignadas,
        "o_pr_muestras_validadas": o_pr_muestras_validadas,
        "o_pr_finalizado": o_pr_finalizado,
        "o_pr_cancelado": o_pr_cancelado,

        "total_recepciones": total_recepciones,
        "total_muestras": total_muestras,

        "total_solicitudes": total_solicitudes,
        "total_ensayos": total_ensayos,
        "total_ensayos_pendiente": total_ensayos_pendiente,
        "total_ensayos_proceso": total_ensayos_proceso,
        "total_ensayos_finalizado": total_ensayos_finalizado,

        "p_e_finalizado": p_e_finalizado,
        "p_e_proceso": p_e_proceso,
        "p_e_pendiente": p_e_pendiente,
        "o_e_proceso": o_e_proceso,
        "o_e_pendiente": o_e_pendiente,

        "total_incidencias": total_incidencias,
        "total_incidencias_autorizadas": total_incidencias_autorizadas,
        "total_incidencias_pendientes": total_incidencias_pendientes,

        "total_informes": total_informes,
        "total_informes_pendientes_envio": total_informes_pendientes_envio,
        "total_informes_enviados": total_informes_enviados,

        "proyectos_con_muestras": proyectos_con_muestras,
        "proyectos_con_solicitud": proyectos_con_solicitud,
        "proyectos_con_informe": proyectos_con_informe,
        "proyectos_sin_muestras": proyectos_sin_muestras,
        "proyectos_sin_solicitud": proyectos_sin_solicitud,
        "proyectos_sin_informe": proyectos_sin_informe,

        "p_proyectos_con_muestras": p_proyectos_con_muestras,
        "p_proyectos_con_solicitud": p_proyectos_con_solicitud,
        "p_proyectos_con_informe": p_proyectos_con_informe,

        "solicitudes_vencidas": solicitudes_vencidas,
        "detalles_vencidos": detalles_vencidos,
    }

    return render(request, "dashboard.html", context)

@login_required
def dashboard_view_analitycs(request):
    return render(request, 'administracion.html')