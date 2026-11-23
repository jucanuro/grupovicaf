"""Firmas: personales (varias por usuario) y compartidas por cuenta (las define
quien administra la cuenta)."""
import base64
import uuid

from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from .cuentas import ADMINISTRA, cuentas_de, permite, roles_de
from . import firma_plantilla as plantilla_firma
from .enlaces import url_lab
from .firma_bloque import para_vista
from .models import CuentaCorreo, Firma
from .presentacion import panel_cuentas
from .sanitizar import sanitizar_html
from .views_correo import URLCONF_LAB, _csp_cuerpo, correo_requerido

MAX_FIRMA = 300_000  # ~300 KB con imágenes en base64
MARCO_PREVIA = ('<p>Buenos días,</p><p>Adjunto la información que solicitó. '
                'Quedo atento a cualquier consulta.</p><p>Saludos cordiales,</p>')


def _data_uri(campo):
    """El logo subido como data: para las vistas previas (así se ve igual en
    local y en producción, sin depender de qué host sirve MEDIA)."""
    try:
        with campo.open('rb') as f:
            contenido = f.read()
    except OSError:
        return None
    tipo = 'image/png' if campo.name.lower().endswith('.png') else 'image/jpeg'
    return f'data:{tipo};base64,{base64.b64encode(contenido).decode()}'


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
        nombre = (p.get('nombre_firma') or p.get('nombre') or '').strip()[:80]
        ambito = p.get('ambito', 'personal')
        errores = []
        datos_plantilla = None
        logo_nuevo = None
        if p.get('modo') == 'plantilla':
            datos_plantilla = plantilla_firma.limpiar_datos(p)
            errores += plantilla_firma.errores_de(datos_plantilla, p)
            if request.FILES.get('logo'):
                try:
                    logo_nuevo = plantilla_firma.procesar_logo(request.FILES['logo'])
                except ValueError as e:
                    errores.append(str(e))
            html = ''  # se arma al guardar, cuando ya se conoce la URL del logo
        else:
            html = sanitizar_html(p.get('html', ''))
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
                firma.nombre, firma.plantilla = nombre, datos_plantilla
                if datos_plantilla is None:
                    firma.html = html
                else:
                    if logo_nuevo:
                        if firma.logo:
                            firma.logo.delete(save=False)
                        extension, contenido = logo_nuevo
                        firma.logo.save(f'{uuid.uuid4().hex}.{extension}', ContentFile(contenido), save=False)
                    elif p.get('quitar_logo') and firma.logo:
                        firma.logo.delete(save=False)
                    logo_url = plantilla_firma.url_publica(firma.logo.url) if firma.logo else None
                    firma.html = sanitizar_html(plantilla_firma.generar_html(datos_plantilla, logo_url))
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
    if request.method == 'POST' and request.POST.get('modo') == 'plantilla':
        datos = plantilla_firma.limpiar_datos(request.POST)
        modo = 'plantilla'
    elif firma is not None and firma.plantilla:
        datos, modo = {**plantilla_firma.datos_iniciales(request.user), **firma.plantilla}, 'plantilla'
    elif firma is None and request.GET.get('modo') != 'libre' and request.method != 'POST':
        datos, modo = plantilla_firma.datos_iniciales(request.user), 'plantilla'
    else:
        datos, modo = {}, 'libre'
    return render(request, 'correo/firma_form.html', {
        'cuentas': panel_cuentas(request.user),
        'firma': firma,
        'modo': modo,
        'datos': datos,
        'posiciones': plantilla_firma.POSICIONES,
        'limites_logo': (plantilla_firma.LOGO_ANCHO_MIN, plantilla_firma.LOGO_ANCHO_MAX),
        'campos_texto': [(c, e, n, datos.get(c, '')) for c, e, n in plantilla_firma.CAMPOS_TEXTO],
        'campos_redes': [(c, e, datos.get(c, '')) for c, e, _m in plantilla_firma.CAMPOS_REDES],
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
    html = firma.html
    if firma.plantilla:
        html = para_vista(html, f'{request.scheme}://{request.get_host()}')
    respuesta = HttpResponse(render_to_string('correo/cuerpo.html', {'html': html}))
    respuesta['Content-Security-Policy'] = _csp_cuerpo(request, imagenes=bool(firma.plantilla))
    return respuesta


@require_POST
@xframe_options_sameorigin
@correo_requerido
def firma_previa(request):
    """Vista previa en vivo de la firma con plantilla: recibe el mismo
    formulario que se guarda (con el logo aún sin guardar) y no guarda nada."""
    p = request.POST
    datos = plantilla_firma.limpiar_datos(p)
    logo_url = None
    archivo = request.FILES.get('logo')
    if archivo:
        try:
            extension, contenido = plantilla_firma.procesar_logo(archivo)
            tipo = 'image/png' if extension == 'png' else 'image/jpeg'
            logo_url = f'data:{tipo};base64,{base64.b64encode(contenido).decode()}'
        except ValueError:
            logo_url = None
    elif not p.get('quitar_logo') and (p.get('firma_pk') or '').isdigit():
        firma = _firmas_visibles(request.user).filter(pk=int(p['firma_pk'])).first()
        if firma and firma.logo:
            logo_url = _data_uri(firma.logo)
    origen = f'{request.scheme}://{request.get_host()}'
    html = sanitizar_html(plantilla_firma.generar_html(datos, logo_url, base=origen))
    respuesta = HttpResponse(render_to_string('correo/cuerpo.html', {'html': MARCO_PREVIA + html}))
    respuesta['Content-Security-Policy'] = _csp_cuerpo(request, imagenes=True)
    return respuesta
