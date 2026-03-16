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
    total_clientes = Cliente.objects.count()
    total_cotizaciones = Cotizacion.objects.count()
    total_cotizaciones_pendientes = Cotizacion.objects.filter(estado='Pendiente').count()
    total_cotizaciones_aceptadas = Cotizacion.objects.filter(estado='Aceptada').count()
    
    total_proyectos = Proyecto.objects.count()
    total_muestras = RecepcionMuestra.objects.count()
    total_ensayos = SolicitudEnsayo.objects.count()
    total_ensayos_pendiente = SolicitudEnsayo.objects.filter(estado = 'pendiente').count()
    total_ensayos_proceso = SolicitudEnsayo.objects.filter(estado = 'proceso').count()
    total_ensayos_finalizado = SolicitudEnsayo.objects.filter(estado = 'finalizado').count()
    
    context = {
        "total_clientes" : total_clientes,
        "total_cotizaciones" : total_cotizaciones,
        "total_cotizaciones_pendientes" : total_cotizaciones_pendientes,
        "total_cotizaciones_aceptadas" : total_cotizaciones_aceptadas,
        
        "total_proyectos" : total_proyectos,
        "total_muestras" : total_muestras,
        "total_ensayos" : total_ensayos,
        
        "total_ensayos_pendiente" : total_ensayos_pendiente,
        "total_ensayos_proceso" : total_ensayos_proceso,
        "total_ensayos_finalizado" : total_ensayos_finalizado,
    }
    return render(request, "dashboard.html",context)
    
    

@login_required
def dashboard_view_analitycs(request):
    return render(request, 'administracion.html')