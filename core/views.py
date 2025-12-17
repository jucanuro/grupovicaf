from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.contrib import messages

class CoreLoginView(LoginView):
    template_name = 'core/login.html' 
    
    next_page = reverse_lazy('dashboard') 
    
    def form_invalid(self, form):
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

