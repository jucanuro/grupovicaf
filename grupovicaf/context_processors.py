from django.conf import settings


def site_url(request):
    """Expone SITE_URL para construir canonical/OG absolutos en las plantillas."""
    return {'SITE_URL': settings.SITE_URL.rstrip('/')}
