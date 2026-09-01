from django.shortcuts import render

from servicios.models import Norma, Servicio
from siteconfig.models import NegocioConfig
from web_acreditacion.models import Acreditacion
from web_catalogo.models import LineaServicio
from web_catalogo.views import clientes_destacados

from .models import CarruselInicio


def _metricas_credibilidad():
    """Franja de credibilidad bajo el hero.

    Regla del encargo: si un número no sale de un dato real y verificable de
    la BD, no se muestra. Nada de "+" para inflar, nada de valores por
    defecto inventados. Cada métrica con conteo 0 (o sin registro) se omite.
    """
    metricas = []

    acreditados = Servicio.objects.filter(esta_acreditado=True).count()
    if acreditados:
        metricas.append({'valor': str(acreditados), 'etiqueta': 'Ensayos acreditados'})

    config = NegocioConfig.objects.first()
    if config and config.acreditacion_codigo:
        entidad = (config.acreditacion_entidad or '').strip()
        metricas.append({
            'valor': config.acreditacion_codigo,
            'etiqueta': f'Registro {entidad}'.strip() if entidad else 'Registro de acreditación',
        })

    normas = Norma.objects.count()
    if normas:
        metricas.append({'valor': str(normas), 'etiqueta': 'Normas técnicas'})

    vigencia_hasta = (
        Acreditacion.objects.filter(activo=True, vigencia_hasta__isnull=False)
        .order_by('-vigencia_hasta')
        .values_list('vigencia_hasta', flat=True)
        .first()
    )
    if vigencia_hasta:
        metricas.append({'valor': vigencia_hasta.strftime('%m/%Y'), 'etiqueta': 'Acreditación vigente hasta'})

    return metricas


def inicio_view(request):
    slides = CarruselInicio.objects.vigentes().only(
        'id', 'titulo', 'descripcion', 'imagen', 'alt_text', 'enlace', 'orden',
    )
    lineas = (
        LineaServicio.objects.publicadas()
        .only('slug', 'nombre', 'resumen', 'imagen', 'imagen_alt')
        .order_by('orden', 'nombre')
    )
    return render(request, 'web/home.html', {
        'slides': slides,
        'lineas': lineas,
        'metricas': _metricas_credibilidad(),
        'clientes_destacados': clientes_destacados(),
    })
