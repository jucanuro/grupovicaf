"""Pantalla «Administrar cuentas» del correo (Paso 3). Reglas en correo.administracion."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import administracion as adm
from .enlaces import url_lab
from .models import AccesoCuenta, EventoCuenta
from .presentacion import panel_cuentas
from .views_correo import URLCONF_LAB, correo_requerido


def _contexto(request, **extra):
    return {
        'cuentas': panel_cuentas(request.user),
        'url_inicio_lab': url_lab(request, reverse('inicio', urlconf=URLCONF_LAB)),
        'es_admin_correo': adm.es_admin_correo(request.user),
        'roles': AccesoCuenta.ROLES,
        **extra,
    }


def _exigir_alguna(user):
    if not adm.puede_administrar_algo(user):
        raise PermissionDenied('No administras ninguna cuenta de correo.')


@correo_requerido
def lista(request):
    _exigir_alguna(request.user)
    administrables = (adm.cuentas_administrables(request.user)
                      .annotate(n_accesos=Count('accesos', distinct=True),
                                n_mensajes=Count('mensajes', filter=~Q(mensajes__estado_envio='borrador'), distinct=True))
                      .order_by('-activa', 'nombre'))
    return render(request, 'correo/admin_cuentas.html', _contexto(
        request, administrables=administrables,
        dominios=' o '.join(f'@{d}' for d in settings.CORREO_DOMINIOS),
        bitacora=EventoCuenta.objects.filter(cuenta__in=administrables).select_related('usuario__trabajadorprofile')[:15],
    ))


@require_POST
@correo_requerido
def crear(request):
    try:
        cuenta = adm.crear_cuenta(
            request.user, direccion=request.POST.get('direccion'), nombre=request.POST.get('nombre'),
            darme_acceso=request.POST.get('darme_acceso') == '1',
        )
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
        return redirect('admin_cuentas')
    messages.success(request, f'Cuenta {cuenta.direccion} creada. Ahora da acceso a quienes la atenderán.')
    return redirect('admin_cuenta', cuenta.slug)


@correo_requerido
def detalle(request, slug):
    cuenta = adm.exigir_cuenta_administrable(request.user, slug)
    accesos = list(cuenta.accesos.select_related('usuario__trabajadorprofile')
                   .order_by('usuario__trabajadorprofile__nombre_completo', 'usuario__username'))
    con_acceso = {a.usuario_id for a in accesos}
    return render(request, 'correo/admin_cuenta.html', _contexto(
        request, cuenta=cuenta, accesos=accesos,
        sin_permiso=adm.sin_permiso_correo([a.usuario for a in accesos]),
        candidatos=[u for u in adm.usuarios_asignables() if u.pk not in con_acceso],
        bitacora=cuenta.bitacora.select_related('usuario__trabajadorprofile')[:30],
    ))


@require_POST
@correo_requerido
def guardar(request, slug):
    cuenta = adm.exigir_cuenta_administrable(request.user, slug)
    if 'activa' in request.POST:  # primero lo que exige más permiso: si falla, no cambia nada
        adm.cambiar_estado(request.user, cuenta, request.POST.get('activa') == '1')
    adm.renombrar_cuenta(request.user, cuenta, request.POST.get('nombre'))
    messages.success(request, 'Cuenta actualizada.')
    return redirect('admin_cuenta', cuenta.slug)


@require_POST
@correo_requerido
def acceso_dar(request, slug):
    cuenta = adm.exigir_cuenta_administrable(request.user, slug)
    usuario = get_object_or_404(get_user_model(), pk=request.POST.get('usuario') or 0)
    try:
        adm.dar_acceso(request.user, cuenta, usuario, request.POST.get('rol'))
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, 'Acceso guardado.')
    return redirect('admin_cuenta', cuenta.slug)


def _exigir_acceso(request, slug, pk):
    cuenta = adm.exigir_cuenta_administrable(request.user, slug)
    return get_object_or_404(AccesoCuenta.objects.select_related('usuario__trabajadorprofile', 'cuenta'), pk=pk, cuenta=cuenta)


@require_POST
@correo_requerido
def acceso_rol(request, slug, pk):
    acceso = _exigir_acceso(request, slug, pk)
    try:
        adm.cambiar_rol(request.user, acceso, request.POST.get('rol'))
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, 'Rol actualizado.')
    return redirect('admin_cuenta', slug)


@require_POST
@correo_requerido
def acceso_quitar(request, slug, pk):
    acceso = _exigir_acceso(request, slug, pk)
    try:
        adm.quitar_acceso(request.user, acceso)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, 'Acceso quitado.')
    return redirect('admin_cuenta', slug)
