from django.conf import settings


def site_url(request):
    """Expone SITE_URL y el interruptor SITE_NOINDEX a toda plantilla."""
    return {
        'SITE_URL': settings.SITE_URL.rstrip('/'),
        'site_noindex': settings.SITE_NOINDEX,
    }
