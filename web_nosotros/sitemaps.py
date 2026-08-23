from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Nosotros


class NosotrosSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.8

    def items(self):
        return ['web_nosotros:nosotros']

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        nosotros = Nosotros.objects.only('actualizado').first()
        return nosotros.actualizado if nosotros else None
