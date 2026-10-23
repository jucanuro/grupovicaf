"""Lógica del asistente de WhatsApp de la web (VCF-WEB, D-VCF-004).

Solo lectura: arma el saludo según la hora de Lima y el catálogo público que
el widget muestra. Lista blanca de campos (CLAUDE.md, regla 2): nunca sale
precio, código de facturación, marca de acreditado ni el Servicio del LIMS.
"""
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from web_catalogo.models import LineaServicio, ServicioPublicado

CACHE_CATALOGO = 'asistente:catalogo'
CACHE_CATALOGO_SEGUNDOS = 300


def saludo_para(momento=None):
    """Buenos días 05:00-11:59, Buenas tardes 12:00-18:59, Buenas noches 19:00-04:59 (hora de Lima)."""
    hora = timezone.localtime(momento or timezone.now()).hour
    if 5 <= hora < 12:
        return 'Buenos días'
    if 12 <= hora < 19:
        return 'Buenas tardes'
    return 'Buenas noches'


def _url_servicio(slug):
    return reverse('web_catalogo:servicio_detalle', kwargs={'slug': slug})


def catalogo_publico():
    """Líneas activas con sus ensayos publicados, solo con campos públicos."""
    catalogo = cache.get(CACHE_CATALOGO)
    if catalogo is not None:
        return catalogo

    ensayos_por_linea = {}
    ensayos = (
        ServicioPublicado.objects.publicados()
        .filter(linea__activo=True)
        .order_by('orden', 'titulo_publico')
        .values('linea_id', 'titulo_publico', 'resumen', 'slug')
    )
    for ensayo in ensayos:
        ensayos_por_linea.setdefault(ensayo['linea_id'], []).append({
            'titulo': ensayo['titulo_publico'],
            'resumen': ensayo['resumen'],
            'url': _url_servicio(ensayo['slug']),
        })

    catalogo = [
        {
            'nombre': linea['nombre'],
            'resumen': linea['resumen'],
            'url': _url_servicio(linea['slug']),
            'ensayos': ensayos_por_linea.get(linea['id'], []),
        }
        for linea in LineaServicio.objects.publicadas().order_by('orden', 'nombre').values('id', 'nombre', 'resumen', 'slug')
    ]
    cache.set(CACHE_CATALOGO, catalogo, CACHE_CATALOGO_SEGUNDOS)
    return catalogo


def datos_asistente(negocio, momento=None):
    """Payload del endpoint /contacto/asistente/."""
    return {
        'saludo': saludo_para(momento),
        'abierto': negocio.esta_abierto(momento),
        'horario': negocio.horario_texto(),
        'whatsapp': negocio.whatsapp_digitos,
        'lineas': catalogo_publico(),
    }
