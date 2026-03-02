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

from proyectos.models import Proyecto, RecepcionMuestra, SolicitudEnsayo
from servicios.models import Cotizacion

class CoreLoginView(LoginView):
    template_name = 'core/login.html' 
    next_page = reverse_lazy('dashboard') 
    
    def form_invalid(self, form):
        messages.error(self.request, 'Usuario o contraseña incorrectos. Intente de nuevo.')
        return super().form_invalid(form)


@login_required
def dashboard_view(request):
    total_proyectos = Proyecto.objects.count()
    proyectos_activos = Proyecto.objects.filter(estado='EN_CURSO').count()
    
    total_muestras = RecepcionMuestra.objects.count()
    
    n_proceso = SolicitudEnsayo.objects.filter(estado='proceso').count()
    n_completados = SolicitudEnsayo.objects.filter(estado='finalizado').count()
    n_pendientes = SolicitudEnsayo.objects.filter(estado='pendiente').count()

    hoy = timezone.now().date()
    n_vencidos = Proyecto.objects.filter(
        fecha_entrega_estimada__lt=hoy
    ).exclude(estado='FINALIZADO').count()

    eficiencia = (n_completados / total_muestras * 100) if total_muestras > 0 else 0
    porc_proceso = (n_proceso / total_muestras * 100) if total_muestras > 0 else 0

    hace_6_meses = hoy - datetime.timedelta(days=180)
    data_mensual = (
        RecepcionMuestra.objects.filter(fecha_recepcion__date__gte=hace_6_meses)
        .annotate(mes=TruncMonth('fecha_recepcion'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )

    labels_grafico = [d['mes'].strftime('%b') for d in data_mensual]
    datos_grafico = [d['total'] for d in data_mensual]

    muestras_recientes = RecepcionMuestra.objects.select_related(
        'cotizacion__cliente', 
        'solicitud_ensayo'
    ).order_by('-fecha_recepcion')[:5]

    context = {
        'n_proyectos': total_proyectos,
        'n_activos': proyectos_activos,
        'total_muestras': total_muestras,
        'n_proceso': n_proceso,
        'n_completados': n_completados,
        'n_pendientes': n_pendientes,
        'n_vencidos': n_vencidos,
        'eficiencia_entrega': int(eficiencia),
        'porc_proceso': int(porc_proceso),
        'labels_grafico': labels_grafico,
        'datos_grafico': datos_grafico,
        'muestras_recientes': muestras_recientes,
    }
    
    return render(request, 'dashboard.html', context)

@login_required
def dashboard_view_analitycs(request):
    """ Vista para la sección de administración """
    return render(request, 'administracion.html')