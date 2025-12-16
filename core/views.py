from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.contrib import messages

# Usamos la clase integrada de Django
class CoreLoginView(LoginView):
    # La plantilla del formulario de login. Debes crearla en core/templates/core/login.html
    template_name = 'core/login.html' 
    
    # Redirige a la URL nombrada 'dashboard' (tal como ya lo tienes en settings.py)
    next_page = reverse_lazy('dashboard') 
    
    def form_invalid(self, form):
        # Opcional: Para mensajes de error personalizados
        messages.error(self.request, 'Usuario o contraseña incorrectos. Intente de nuevo.')
        return super().form_invalid(form)

@login_required
def dashboard_view(request):
    """
    Vista del dashboard que solo es accesible para usuarios autenticados.
    """
    return render(request, 'dashboard.html')

@login_required
def dashboard_view_analitycs(request):
    """
    Vista del dashboard que solo es accesible para usuarios autenticados.
    """
    return render(request, 'dashboard_analitycs.html')

