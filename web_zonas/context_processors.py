from django.conf import settings

from .models import ZonaCobertura


def footer_zonas(request):
    """Las 7 zonas de cobertura para los enlaces internos del footer (SEO local,
    regla F9). Sin caché, igual que zonas_list_view: 7 filas, coste despreciable.

    Solo corre en el proceso `web` (ver docstring de footer_lineas en
    web_catalogo.context_processors: mismo motivo, footer.html es solo web).
    """
    if settings.SITE_ROLE != 'web':
        return {}
    zonas = (
        ZonaCobertura.objects.activas()
        .only('slug', 'nombre', 'es_sede')
        .order_by('-es_sede', 'orden', 'nombre')
    )
    return {'footer_zonas': zonas}
