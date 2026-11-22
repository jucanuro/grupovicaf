from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.shortcuts import render
from django.utils import timezone

from .dashboard import construir_dashboard, resolver_periodo
from .notificaciones import avisos_de


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


class CambiarClaveForm(PasswordChangeForm):
    """Cambio de contraseña propio: la nueva no puede ser igual a la actual."""

    def clean_new_password2(self):
        nueva = super().clean_new_password2()
        if nueva and nueva == self.cleaned_data.get('old_password'):
            raise ValidationError('La nueva contraseña debe ser distinta de la actual.', code='igual')
        return nueva


class CambiarClaveView(PasswordChangeView):
    """«Cambiar mi contraseña»: la ve cualquier usuario con sesión; apaga el aviso de clave temporal."""
    template_name = 'registration/cambiar_clave.html'
    form_class = CambiarClaveForm
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        from trabajadores.models import TrabajadorProfile
        respuesta = super().form_valid(form)
        TrabajadorProfile.objects.filter(user=self.request.user).update(debe_cambiar_clave=False)
        messages.success(self.request, 'Tu contraseña se cambió correctamente.')
        return respuesta

    def get_context_data(self, **kwargs):
        from trabajadores.models import TrabajadorProfile
        contexto = super().get_context_data(**kwargs)
        contexto['obligatorio'] = TrabajadorProfile.objects.filter(
            user=self.request.user, debe_cambiar_clave=True).exists()
        return contexto


@login_required
def notificaciones_json(request):
    """Avisos de la campana de la cabecera (ver core/notificaciones.py)."""
    avisos = avisos_de(request.user)
    return JsonResponse({'total': sum(a['cantidad'] for a in avisos), 'avisos': avisos})
