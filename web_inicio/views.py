from django.shortcuts import render

from clientes.models import Cliente
from servicios.models import Servicio
from web_catalogo.models import LineaServicio
from web_catalogo.views import clientes_destacados
from web_zonas.models import ZonaCobertura

from .models import CarruselInicio


def _metricas_credibilidad():
    """Cifras reales para la franja de credibilidad bajo el hero.

    Solo entran métricas con dato real y distinto de cero: un "0 clientes
    atendidos" no acredita nada y contradice la franja (regla del encargo:
    "si un dato no existe en BD, no lo inventes, omite esa métrica").
    """
    candidatas = (
        (Servicio.objects.filter(esta_acreditado=True).count(), 'Ensayos acreditados', '+'),
        (Cliente.objects.count(), 'Clientes atendidos', '+'),
        (ZonaCobertura.objects.activas().count(), 'Zonas de cobertura', ''),
    )
    return [
        {'valor': valor, 'etiqueta': etiqueta, 'sufijo': sufijo}
        for valor, etiqueta, sufijo in candidatas
        if valor
    ]


def inicio_view(request):
    slides = CarruselInicio.objects.vigentes().only(
        'id', 'titulo', 'descripcion', 'imagen', 'alt_text', 'enlace', 'orden',
    )
    lineas = (
        LineaServicio.objects.publicadas()
        .only('slug', 'nombre', 'resumen', 'imagen', 'imagen_alt')
        .order_by('orden', 'nombre')
    )
    zonas = (
        ZonaCobertura.objects.activas()
        .only('slug', 'nombre', 'es_sede')
        .order_by('-es_sede', 'orden', 'nombre')
    )
    return render(request, 'web/home.html', {
        'slides': slides,
        'lineas': lineas,
        'zonas': zonas,
        'metricas': _metricas_credibilidad(),
        'clientes_destacados': clientes_destacados(),
    })
