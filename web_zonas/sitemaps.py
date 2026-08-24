from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import ZonaCobertura


class ZonaCoberturaSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.8

    def items(self):
        return ZonaCobertura.objects.activas().only('slug', 'actualizado')

    def location(self, item):
        return reverse('web_zonas:zona_detalle', kwargs={'slug': item.slug})

    def lastmod(self, item):
        return item.actualizado


class ZonasListadoSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return ['web_zonas:zonas_list']

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        ultimo = ZonaCobertura.objects.activas().only('actualizado').order_by('-actualizado').first()
        return ultimo.actualizado if ultimo else None
