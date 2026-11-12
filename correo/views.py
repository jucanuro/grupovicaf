"""Vistas del host del LIMS (laboratorio.<dominio>): pantalla de entrada y
salto firmado hacia el correo."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .cuentas import cuenta_de, cuentas_de
from .enlaces import crear_enlace, destino_seguro, url_correo
from .permisos import puede_usar_correo, puede_usar_sistema


@login_required
def inicio(request):
    """Pantalla de entrada tras el login: tarjetas Correos y Sistema (LIMS)."""
    user = request.user
    ve_correo = puede_usar_correo(user)
    ve_sistema = puede_usar_sistema(user)

    if settings.CORREO_OMITIR_ENTRADA and ve_correo != ve_sistema:
        return redirect('correo:abrir' if ve_correo else 'dashboard')

    cuentas = cuentas_de(user) if ve_correo else []
    return render(request, 'correo/inicio.html', {
        've_correo': ve_correo,
        've_sistema': ve_sistema,
        'cuentas': cuentas,
        'total_no_leidos': sum(c.no_leidos for c in cuentas),
        'nombre_usuario': _nombre(user),
    })


@login_required
def abrir(request):
    """Emite el enlace firmado y redirige al host del correo.

    ?cuenta=<slug> abre esa cuenta; ?next=/ruta abre una ruta interna del
    correo (la usa el login del host de correo para volver a donde estaba).
    """
    if not puede_usar_correo(request.user):
        return render(request, 'correo/sin_acceso.html', status=403)

    slug = request.GET.get('cuenta')
    if slug:
        if cuenta_de(request.user, slug) is None:
            raise Http404('Cuenta no disponible.')
        destino = reverse('bandeja_cuenta', urlconf='grupovicaf.urls_correo', args=[slug])
    else:
        destino = destino_seguro(request.GET.get('next', '/'))

    token = crear_enlace(request.user, destino)
    entrar = reverse('entrar', urlconf='grupovicaf.urls_correo')
    return redirect(url_correo(request, entrar, t=token))


def _nombre(user):
    perfil = getattr(user, 'trabajadorprofile', None)
    return (getattr(perfil, 'nombre_completo', '') or user.get_full_name() or user.username).split(' ')[0]
