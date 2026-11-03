from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.utils import timezone

from .dashboard import construir_dashboard, resolver_periodo


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
    """Dashboard del LIMS: los cálculos viven en core/dashboard.py (VCF-LIMS)."""
    hoy = timezone.localdate()
    periodo = resolver_periodo(request.GET, hoy)
    contexto = construir_dashboard(periodo, request.user, hoy)
    return render(request, "dashboard.html", contexto)


@login_required
def dashboard_view_analitycs(request):
    return render(request, 'administracion.html')