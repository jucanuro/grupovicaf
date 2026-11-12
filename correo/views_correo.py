"""Vistas del host del correo (email.<dominio>), URLconf grupovicaf.urls_correo.

Paso 1: solo el ingreso por enlace firmado y una bandeja provisional. La
interfaz completa (tres paneles) llega en el Paso 2.
"""
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .cuentas import cuenta_de, cuentas_de
from .enlaces import consumir_enlace, destino_seguro, url_lab
from .permisos import puede_usar_correo

BACKEND = 'django.contrib.auth.backends.ModelBackend'


def ir_al_login(request):
    """LOGIN_URL del host de correo: el login vive en el LIMS.

    Manda a laboratorio./correo/abrir/?next=<ruta>; si ya hay sesión allí,
    vuelve en seguida con un enlace firmado; si no, pasa antes por el login.
    """
    abrir = reverse('correo:abrir', urlconf='grupovicaf.urls_lab')
    return redirect(url_lab(request, abrir, next=destino_seguro(request.GET.get('next', '/'))))


@never_cache
def entrar(request):
    """Consume el enlace firmado y abre la sesión propia del host de correo."""
    datos = consumir_enlace(request.GET.get('t'))
    if datos is None:
        return render(request, 'correo/enlace_invalido.html', {
            'url_lab': url_lab(request, reverse('inicio', urlconf='grupovicaf.urls_lab')),
        }, status=400)

    user = get_user_model().objects.filter(pk=datos['u'], is_active=True).first()
    if user is None or not puede_usar_correo(user):
        return render(request, 'correo/sin_acceso.html', status=403)

    login(request, user, backend=BACKEND)  # rota la clave de sesión
    return redirect(datos['d'])


@login_required
def bandeja(request, cuenta=None):
    if not puede_usar_correo(request.user):
        return render(request, 'correo/sin_acceso.html', status=403)

    cuentas = cuentas_de(request.user)
    actual = None
    if cuenta is not None:
        actual = cuenta_de(request.user, cuenta)
        if actual is None:
            # 404 y no 403: no revelar que la cuenta existe.
            raise Http404('Cuenta no disponible.')

    return render(request, 'correo/bandeja_provisional.html', {
        'cuentas': cuentas,
        'actual': actual,
        'no_leidos': actual.no_leidos if actual else sum(c.no_leidos for c in cuentas),
        'url_inicio_lab': url_lab(request, reverse('inicio', urlconf='grupovicaf.urls_lab')),
    })


@require_POST
def salir(request):
    """Cierra la sesión del correo (la del LIMS se cierra en el LIMS)."""
    logout(request)
    return redirect(url_lab(request, reverse('inicio', urlconf='grupovicaf.urls_lab')))
