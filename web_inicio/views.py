from django.shortcuts import render

from servicios.models import Norma, Servicio
from siteconfig.models import NegocioConfig
from web_acreditacion.models import Acreditacion, Certificacion, primera_acreditacion
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

    config = NegocioConfig.objects.first()

    # NegocioConfig.ensayos_acreditados manda si está definido: el conteo por
    # Servicio.esta_acreditado no es confiable mientras ese flag siga mal
    # poblado en el LIMS (ver el comentario del campo en siteconfig.models).
    if config and config.ensayos_acreditados is not None:
        acreditados = config.ensayos_acreditados
    else:
        acreditados = Servicio.objects.filter(esta_acreditado=True).count()
    if acreditados:
        metricas.append({'valor': str(acreditados), 'etiqueta': 'Ensayos acreditados'})

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
    # Versión resumida de /acreditacion/ (REQ-WEB-49): una consulta, máximo 4 cards.
    certificaciones = list(Certificacion.objects.publicadas().para_card())
    return render(request, 'web/home.html', {
        'slides': slides,
        'lineas': lineas,
        'metricas': _metricas_credibilidad(),
        'clientes_destacados': clientes_destacados(),
        'certificaciones': certificaciones[:4],
        'certificacion_acreditacion': primera_acreditacion(certificaciones),
    })
