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
from django.db.models import Q
from clientes.models import Cliente
from proyectos.models import Proyecto, RecepcionMuestra,MuestraDetalle, SolicitudEnsayo,DetalleSolicitudEnsayo,IncidenciaSolicitud, InformeFinal
from servicios.models import Cotizacion

class CoreLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = False

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')

        if next_url:
            return next_url

        return super().get_success_url()

    def form_invalid(self, form):
        messages.error(self.request, 'Usuario o contraseña incorrectos. Intente de nuevo.')
        return super().form_invalid(form)

@login_required
def dashboard_view(request):
    def obtener_fechas(prefix):
        return (
            request.GET.get(f'inicio_{prefix}', '').strip(),
            request.GET.get(f'fin_{prefix}', '').strip()
        )

    def parsear_fecha(valor):
        if not valor:
            return None
        try:
            return datetime.strptime(valor, '%Y-%m-%d').date()
        except ValueError:
            return None

    def obtener_campo_fecha(modelo, candidatos=None):
        if candidatos is None:
            candidatos = [
                'fecha_creacion',
                'created_at',
                'fecha',
                'created',
                'fecha_registro',
                'fecha_emision',
                'fecha_ingreso',
                'fecha_solicitud',
                'f_creacion',
            ]
        campos_modelo = {field.name for field in modelo._meta.get_fields()}
        for campo in candidatos:
            if campo in campos_modelo:
                return campo
        return None

    def aplicar_filtro_rango(qs, modelo, fecha_inicio, fecha_fin, candidatos=None):
        campo_fecha = obtener_campo_fecha(modelo, candidatos=candidatos)
        if not campo_fecha:
            return qs

        try:
            field = modelo._meta.get_field(campo_fecha)
            es_datetime = field.get_internal_type() == 'DateTimeField'
        except Exception:
            es_datetime = False

        lookup_base = f'{campo_fecha}__date' if es_datetime else campo_fecha

        if fecha_inicio and fecha_fin:
            return qs.filter(**{f'{lookup_base}__range': [fecha_inicio, fecha_fin]})
        elif fecha_inicio:
            return qs.filter(**{f'{lookup_base}__gte': fecha_inicio})
        elif fecha_fin:
            return qs.filter(**{f'{lookup_base}__lte': fecha_fin})

        return qs

    inicio_1_raw, fin_1_raw = obtener_fechas(1)
    inicio_2_raw, fin_2_raw = obtener_fechas(2)
    inicio_3_raw, fin_3_raw = obtener_fechas(3)

    inicio_1 = parsear_fecha(inicio_1_raw)
    fin_1 = parsear_fecha(fin_1_raw)
    inicio_2 = parsear_fecha(inicio_2_raw)
    fin_2 = parsear_fecha(fin_2_raw)
    inicio_3 = parsear_fecha(inicio_3_raw)
    fin_3 = parsear_fecha(fin_3_raw)

    total_clientes = Cliente.objects.count()

    cotizaciones_qs = Cotizacion.objects.all()
    cotizaciones_qs = aplicar_filtro_rango(
        cotizaciones_qs,
        Cotizacion,
        inicio_1,
        fin_1,
        candidatos=['fecha_creacion', 'created_at', 'fecha', 'fecha_emision', 'created']
    )

    total_cotizaciones = cotizaciones_qs.count()
    total_cotizaciones_pendientes = cotizaciones_qs.filter(estado='Pendiente').count()
    total_cotizaciones_aceptadas = cotizaciones_qs.filter(estado='Aceptada').count()

    proyectos_base_qs = Proyecto.objects.all()
    proyectos_base_qs = aplicar_filtro_rango(
        proyectos_base_qs,
        Proyecto,
        inicio_3,
        fin_3,
        candidatos=['fecha_creacion', 'created_at', 'fecha', 'fecha_inicio', 'created']
    )

    total_proyectos = proyectos_base_qs.count()

    recepciones_qs = RecepcionMuestra.objects.all()
    recepciones_qs = aplicar_filtro_rango(
        recepciones_qs,
        RecepcionMuestra,
        inicio_3,
        fin_3,
        candidatos=['fecha_creacion', 'created_at', 'fecha', 'fecha_recepcion', 'created']
    )
    total_recepciones = recepciones_qs.count()

    muestras_qs = MuestraDetalle.objects.all()
    muestras_qs = aplicar_filtro_rango(
        muestras_qs,
        MuestraDetalle,
        inicio_3,
        fin_3,
        candidatos=['fecha_creacion', 'created_at', 'fecha', 'created']
    )
    total_muestras = muestras_qs.count()

    total_proyectos_pendiente = 0
    total_proyectos_en_curso = 0
    total_proyectos_muestras_asignadas = 0
    total_proyectos_muestras_validadas = 0
    total_proyectos_finalizado = 0
    total_proyectos_cancelado = 0

    proyectos_qs = proyectos_base_qs.select_related('cotizacion').prefetch_related(
        'cotizacion__recepciones__muestras',
        'cotizacion__solicitudes_ensayo',
        'cotizacion__solicitudes_ensayo__informe_final'
    )

    for proyecto in proyectos_qs:
        if proyecto.estado == 'CANCELADO':
            total_proyectos_cancelado += 1
            continue

        cotizacion = proyecto.cotizacion
        if not cotizacion:
            total_proyectos_pendiente += 1
            continue

        recepciones = cotizacion.recepciones.all()
        tiene_muestras = any(r.muestras.exists() for r in recepciones)

        solicitudes = list(cotizacion.solicitudes_ensayo.all())
        solicitud = solicitudes[0] if solicitudes else None

        if solicitud:
            if solicitud.estado in ['pendiente', 'proceso']:
                total_proyectos_en_curso += 1
                continue

            if solicitud.estado == 'finalizado':
                informe = InformeFinal.objects.filter(solicitud=solicitud).first()
                if informe:
                    total_proyectos_finalizado += 1
                else:
                    total_proyectos_muestras_validadas += 1
                continue

        if tiene_muestras:
            total_proyectos_muestras_asignadas += 1
        else:
            total_proyectos_pendiente += 1

    solicitudes_qs = SolicitudEnsayo.objects.all()
    solicitudes_qs = aplicar_filtro_rango(
        solicitudes_qs,
        SolicitudEnsayo,
        inicio_2,
        fin_2,
        candidatos=['fecha_creacion', 'created_at', 'fecha', 'fecha_solicitud', 'created']
    )

    total_solicitudes = solicitudes_qs.count()
    total_ensayos_pendiente = solicitudes_qs.filter(estado='pendiente').count()
    total_ensayos_proceso = solicitudes_qs.filter(estado='proceso').count()
    total_ensayos_finalizado = solicitudes_qs.filter(estado='finalizado').count()

    detalles_ensayo_qs = DetalleSolicitudEnsayo.objects.all()
    detalles_ensayo_qs = aplicar_filtro_rango(
        detalles_ensayo_qs,
        DetalleSolicitudEnsayo,
        inicio_2,
        fin_2,
        candidatos=['fecha_creacion', 'created_at', 'fecha', 'created']
    )
    total_ensayos = detalles_ensayo_qs.count()

    incidencias_qs = IncidenciaSolicitud.objects.all()
    incidencias_qs = aplicar_filtro_rango(
        incidencias_qs,
        IncidenciaSolicitud,
        inicio_2,
        fin_2,
        candidatos=['fecha_creacion', 'created_at', 'fecha', 'created']
    )

    total_incidencias = incidencias_qs.count()
    total_incidencias_autorizadas = incidencias_qs.filter(esta_autorizada=True).count()
    total_incidencias_pendientes = incidencias_qs.filter(esta_autorizada=False).count()

    informes_qs = InformeFinal.objects.all()
    informes_qs = aplicar_filtro_rango(
        informes_qs,
        InformeFinal,
        inicio_2,
        fin_2,
        candidatos=['fecha_creacion', 'created_at', 'fecha', 'created', 'fecha_emision']
    )

    total_informes = informes_qs.count()
    total_informes_pendientes_envio = informes_qs.filter(estado_envio='pendiente').count()
    total_informes_enviados = informes_qs.filter(estado_envio='enviado').count()

    proyectos_con_muestras = proyectos_base_qs.filter(
        cotizacion__recepciones__muestras__isnull=False
    ).distinct().count()

    proyectos_con_solicitud = proyectos_base_qs.filter(
        cotizacion__solicitudes_ensayo__isnull=False
    ).distinct().count()

    proyectos_con_informe = proyectos_base_qs.filter(
        cotizacion__solicitudes_ensayo__informe_final__isnull=False
    ).distinct().count()

    proyectos_sin_muestras = total_proyectos - proyectos_con_muestras
    proyectos_sin_solicitud = total_proyectos - proyectos_con_solicitud
    proyectos_sin_informe = total_proyectos - proyectos_con_informe

    solicitudes_vencidas = solicitudes_qs.filter(
        estado__in=['pendiente', 'proceso'],
        fecha_entrega_programada__lt=timezone.now().date()
    ).count()

    detalles_vencidos = detalles_ensayo_qs.filter(
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

        "inicio_1": inicio_1_raw,
        "fin_1": fin_1_raw,
        "inicio_2": inicio_2_raw,
        "fin_2": fin_2_raw,
        "inicio_3": inicio_3_raw,
        "fin_3": fin_3_raw,
    }

    return render(request, "dashboard.html", context)

@login_required
def dashboard_view_analitycs(request):
    return render(request, 'administracion.html')