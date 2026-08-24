from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class ContactoSitemap(Sitemap):
    """/contacto/ — página de conversión, sin lastmod porque es estática (regla 13)."""

    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return ['web_contacto:contacto']

    def location(self, item):
        return reverse(item)
