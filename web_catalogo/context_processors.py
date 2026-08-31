from django.conf import settings

from .views import lineas_sidebar


def footer_lineas(request):
    """Las 8 líneas de servicio para los enlaces internos del footer (SEO, regla F9).

    Solo corre en el proceso `web`: este context processor está registrado en
    settings/base.py, compartido con `lab`, y templates/web/footer.html no se
    renderiza nunca ahí — evita una consulta cacheada de sobra en cada vista LIMS.
    """
    if settings.SITE_ROLE != 'web':
        return {}
    return {'footer_lineas': lineas_sidebar()}
