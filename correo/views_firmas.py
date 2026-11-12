"""Firmas: personales (varias por usuario) y compartidas por cuenta (las define
quien administra la cuenta)."""
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from .cuentas import ADMINISTRA, cuentas_de, permite, roles_de
from .enlaces import url_lab
from .models import CuentaCorreo, Firma
from .presentacion import panel_cuentas
from .sanitizar import sanitizar_html
from .views_correo import URLCONF_LAB, _csp_cuerpo, correo_requerido

MAX_FIRMA = 300_000  # ~300 KB con imágenes en base64


def _cuentas_administradas(user):
    roles = roles_de(user)
    return [c for c in cuentas_de(user) if permite(roles.get(c.pk), ADMINISTRA)]


def _firmas_visibles(user):
    return Firma.objects.filter(Q(usuario=user) | Q(cuenta__in=cuentas_de(user).values('pk')))


def _exigir_firma(user, pk, editar=False):
    firma = _firmas_visibles(user).select_related('cuenta').filter(pk=pk).first()
    if firma is None:
        raise Http404
    if editar and firma.cuenta_id and firma.cuenta_id not in {c.pk for c in _cuentas_administradas(user)}:
        raise Http404
    return firma


@correo_requerido
def firmas(request):
    administradas = _cuentas_administradas(request.user)
    return render(request, 'correo/firmas.html', {
        'cuentas': panel_cuentas(request.user),
        'personales': Firma.objects.filter(usuario=request.user),
        'compartidas': Firma.objects.filter(cuenta__in=cuentas_de(request.user).values('pk')).select_related('cuenta'),
        'administradas': {c.pk for c in administradas},
        'url_inicio_lab': url_lab(request, reverse('inicio', urlconf=URLCONF_LAB)),
    })


@correo_requerido
def firma_editar(request, pk=None):
    firma = _exigir_firma(request.user, pk, editar=True) if pk else None
    administradas = _cuentas_administradas(request.user)
    if request.method == 'POST':
        p = request.POST
        nombre = (p.get('nombre') or '').strip()[:80]
        html = sanitizar_html(p.get('html', ''))
        ambito = p.get('ambito', 'personal')
        errores = []
        if not nombre:
            errores.append('Ponle un nombre a la firma.')
        if len(html) > MAX_FIRMA:
            errores.append('La firma es muy pesada: usa imágenes más livianas (máx. 300 KB).')
        cuenta = None
        if ambito != 'personal':
            cuenta = next((c for c in administradas if str(c.pk) == ambito), None)
            if cuenta is None:
                errores.append('Solo quien administra una cuenta define su firma compartida.')
        if not errores:
            with transaction.atomic():
                firma = firma or Firma()
                firma.nombre, firma.html = nombre, html
                firma.usuario, firma.cuenta = (None, cuenta) if cuenta else (request.user, None)
                firma.para_nuevos = bool(p.get('para_nuevos')) and cuenta is None
                firma.para_respuestas = bool(p.get('para_respuestas')) and cuenta is None
                firma.save()
                if cuenta is None:
                    # Solo una predeterminada de cada tipo por usuario.
                    if firma.para_nuevos:
                        Firma.objects.filter(usuario=request.user).exclude(pk=firma.pk).update(para_nuevos=False)
                    if firma.para_respuestas:
                        Firma.objects.filter(usuario=request.user).exclude(pk=firma.pk).update(para_respuestas=False)
                elif p.get('predeterminada_cuenta'):
                    CuentaCorreo.objects.filter(pk=cuenta.pk).update(firma_predeterminada=firma)
            messages.success(request, 'Firma guardada.')
            return redirect('firmas')
        for e in errores:
            messages.error(request, e)
    return render(request, 'correo/firma_form.html', {
        'cuentas': panel_cuentas(request.user),
        'firma': firma,
        'administradas': administradas,
        'url_inicio_lab': url_lab(request, reverse('inicio', urlconf=URLCONF_LAB)),
    })


@require_POST
@correo_requerido
def firma_eliminar(request, pk):
    firma = _exigir_firma(request.user, pk, editar=True)
    firma.delete()
    messages.success(request, 'Firma eliminada.')
    return redirect('firmas')


@xframe_options_sameorigin
@correo_requerido
def firma_vista(request, pk):
    """Vista previa aislada (iframe) con los estilos de la firma."""
    firma = _exigir_firma(request.user, pk)
    respuesta = HttpResponse(render_to_string('correo/cuerpo.html', {'html': firma.html}))
    respuesta['Content-Security-Policy'] = _csp_cuerpo(request, imagenes=False)
    return respuesta
