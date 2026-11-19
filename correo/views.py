"""Vistas del host del LIMS (laboratorio.<dominio>): pantalla de entrada y
salto firmado hacia el correo."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .cuentas import cuenta_de, cuentas_de, roles_de
from .models import AccesoCuenta
from .enlaces import crear_enlace, destino_seguro, url_correo
from .permisos import motivo_sin_correo, puede_entrar_correo, puede_usar_correo, puede_usar_sistema


VISIBLES = 3  # cuentas a la vista en la tarjeta Correos; el resto va como «+N»


@login_required
def inicio(request):
    """Pantalla de entrada tras el login: tarjetas Correos y Sistema (LIMS).

    La tarjeta Correos lista las cuentas que la persona maneja (máximo 3 a la
    vista, el resto como «+N»). Sin cuentas asignadas la tarjeta queda
    bloqueada: no hay correo que abrir hasta que un administrador le dé acceso.
    """
    user = request.user
    ve_correo = puede_usar_correo(user)
    ve_sistema = puede_usar_sistema(user)
    entra_correo = ve_correo and puede_entrar_correo(user)

    if settings.CORREO_OMITIR_ENTRADA and entra_correo != ve_sistema:
        return redirect('correo:abrir' if entra_correo else 'dashboard')

    cuentas = list(cuentas_de(user)) if ve_correo else []
    roles, textos = roles_de(user), {
        AccesoCuenta.LECTURA: 'Lectura', AccesoCuenta.GESTIONA: 'Gestiona', AccesoCuenta.ADMINISTRA: 'Administra',
    }
    for cuenta in cuentas:
        cuenta.rol_texto = textos.get(roles.get(cuenta.pk), '')
    return render(request, 'correo/inicio.html', {
        've_correo': ve_correo,
        've_sistema': ve_sistema,
        'entra_correo': entra_correo,
        'cuentas': cuentas,
        'cuentas_visibles': cuentas[:VISIBLES],
        'cuentas_resto': max(0, len(cuentas) - VISIBLES),
        'total_no_leidos': sum(c.no_leidos for c in cuentas),
        'nombre_usuario': _nombre(user),
    })


@login_required
def abrir(request):
    """Emite el enlace firmado y redirige al host del correo.

    ?cuenta=<slug> abre esa cuenta; ?next=/ruta abre una ruta interna del
    correo (la usa el login del host de correo para volver a donde estaba).
    """
    if not puede_entrar_correo(request.user):
        return render(request, 'correo/sin_acceso.html', {'motivo': motivo_sin_correo(request.user)}, status=403)

    slug = request.GET.get('cuenta')
    if slug:
        if cuenta_de(request.user, slug) is None:
            raise Http404('Cuenta no disponible.')
        destino = reverse('bandeja_cuenta', urlconf='grupovicaf.urls_correo', args=[slug])
    elif 'next' not in request.GET and not cuentas_de(request.user).exists():
        # Administra el correo pero aún no tiene cuentas: directo a crearlas.
        destino = reverse('admin_cuentas', urlconf='grupovicaf.urls_correo')
    else:
        destino = destino_seguro(request.GET.get('next', '/'))

    token = crear_enlace(request.user, destino)
    entrar = reverse('entrar', urlconf='grupovicaf.urls_correo')
    return redirect(url_correo(request, entrar, t=token))


def _nombre(user):
    perfil = getattr(user, 'trabajadorprofile', None)
    return (getattr(perfil, 'nombre_completo', '') or user.get_full_name() or user.username).split(' ')[0]
