from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Acreditacion


class AcreditacionSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.9

    def items(self):
        return ['web_acreditacion:acreditacion']

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        acreditacion = Acreditacion.objects.filter(activo=True).only('actualizado').order_by('-actualizado').first()
        return acreditacion.actualizado if acreditacion else None
