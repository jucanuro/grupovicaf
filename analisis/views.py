"""Pantalla Análisis del LIMS: tabla dinámica sobre los conjuntos de
`analisis/conjuntos.py` (VCF-LIMS, HU-LIMS-06 a 10).

El servidor solo entrega filas planas con la lista blanca de cada conjunto;
la tabla dinámica, los gráficos y la exportación a Excel corren en el
navegador (static/js/analisis.js).
"""
import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from trabajadores.permissions import permiso_requerido

from .conjuntos import CONJUNTOS, LIMITE_FILAS, PERMISO_REPORTES, FilasExcedidas, conjuntos_para
from .models import VistaAnalisis

MAX_VISTAS_POR_USUARIO = 50
MAX_CONFIG_BYTES = 20_000
CLAVES_CONFIG = {'rows', 'cols', 'vals', 'aggregatorName', 'rendererName',
                 'exclusions', 'inclusions', 'rowOrder', 'colOrder'}


def _conjunto_o_404(clave, user):
    conjunto = CONJUNTOS.get(clave)
    if conjunto is None:
        raise Http404('Conjunto inexistente.')
    return conjunto if conjunto.puede_ver(user) else None


def _prohibido():
    return JsonResponse({'error': 'No tienes permiso para ver este conjunto de datos.'}, status=403)


def _fecha(texto):
    if not texto:
        return None
    return date.fromisoformat(texto)


@login_required
@permiso_requerido(PERMISO_REPORTES)
@require_GET
def analisis_view(request):
    conjuntos = conjuntos_para(request.user)
    config = {
        'conjuntos': [c.resumen(request.user) for c in conjuntos],
        'urls': {
            'datos': reverse('analisis:datos', args=['__conjunto__']),
            'vistas': reverse('analisis:vistas'),
            'eliminar': reverse('analisis:eliminar_vista', args=[0]),
        },
        'limite': LIMITE_FILAS,
    }
    return render(request, 'analisis/analisis.html', {'config': config, 'hay_conjuntos': bool(conjuntos)})


@login_required
@permiso_requerido(PERMISO_REPORTES)
@require_GET
def datos_view(request, clave):
    conjunto = _conjunto_o_404(clave, request.user)
    if conjunto is None:
        return _prohibido()
    try:
        desde = _fecha(request.GET.get('desde'))
        hasta = _fecha(request.GET.get('hasta'))
    except ValueError:
        return JsonResponse({'error': 'Las fechas deben tener el formato AAAA-MM-DD.'}, status=400)
    if desde and hasta and desde > hasta:
        return JsonResponse({'error': 'La fecha "desde" es posterior a "hasta".'}, status=400)
    try:
        datos = conjunto.datos(request.user, desde, hasta)
    except FilasExcedidas as exc:
        return JsonResponse({
            'error': f'El rango tiene {exc.total:,} filas; el máximo es {LIMITE_FILAS:,}. Acota las fechas.',
        }, status=400)
    datos['conjunto'] = conjunto.clave
    return JsonResponse(datos)


def _limpiar_config(config):
    """Solo disposición de la tabla, nunca datos (CA-08.2)."""
    if not isinstance(config, dict):
        raise ValueError('Configuración inválida.')
    limpia = {}
    for clave, valor in config.items():
        if clave not in CLAVES_CONFIG:
            continue
        if clave in ('rows', 'cols', 'vals'):
            if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
                raise ValueError(f'"{clave}" debe ser una lista de textos.')
        elif clave in ('exclusions', 'inclusions'):
            if not isinstance(valor, dict) or not all(
                isinstance(v, list) and all(isinstance(x, str) for x in v) for v in valor.values()
            ):
                raise ValueError(f'"{clave}" tiene un formato inválido.')
        elif not isinstance(valor, str):
            raise ValueError(f'"{clave}" debe ser texto.')
        limpia[clave] = valor
    if len(json.dumps(limpia)) > MAX_CONFIG_BYTES:
        raise ValueError('La configuración es demasiado grande.')
    return limpia


def _vista_json(vista):
    return {'id': vista.pk, 'nombre': vista.nombre, 'conjunto': vista.conjunto,
            'configuracion': vista.configuracion}


@login_required
@permiso_requerido(PERMISO_REPORTES)
def vistas_view(request):
    """GET: vistas del usuario. POST (JSON): guarda o reemplaza una vista."""
    if request.method == 'GET':
        claves = {c.clave for c in conjuntos_para(request.user)}
        vistas = VistaAnalisis.objects.filter(usuario=request.user, conjunto__in=claves)
        return JsonResponse({'vistas': [_vista_json(v) for v in vistas]})
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)

    try:
        cuerpo = json.loads(request.body or b'{}')
        nombre = str(cuerpo.get('nombre', '')).strip()
        if not nombre or len(nombre) > 80:
            raise ValueError('El nombre es obligatorio y tiene como máximo 80 caracteres.')
        conjunto = _conjunto_o_404(str(cuerpo.get('conjunto', '')), request.user)
        if conjunto is None:
            return _prohibido()
        config = _limpiar_config(cuerpo.get('configuracion'))
    except (ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    existente = VistaAnalisis.objects.filter(usuario=request.user, conjunto=conjunto.clave, nombre=nombre).first()
    if existente is None and VistaAnalisis.objects.filter(usuario=request.user).count() >= MAX_VISTAS_POR_USUARIO:
        return JsonResponse({'error': f'Máximo {MAX_VISTAS_POR_USUARIO} vistas por usuario.'}, status=400)
    try:
        vista, _ = VistaAnalisis.objects.update_or_create(
            usuario=request.user, conjunto=conjunto.clave, nombre=nombre,
            defaults={'configuracion': config},
        )
    except IntegrityError:
        return JsonResponse({'error': 'No se pudo guardar la vista.'}, status=400)
    return JsonResponse({'vista': _vista_json(vista)}, status=201)


@login_required
@permiso_requerido(PERMISO_REPORTES)
@require_POST
def eliminar_vista_view(request, pk):
    vista = get_object_or_404(VistaAnalisis, pk=pk, usuario=request.user)
    vista.delete()
    return JsonResponse({'ok': True})
