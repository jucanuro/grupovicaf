from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class InicioSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 1.0

    def items(self):
        return ['web_home']

    def location(self, item):
        return reverse(item)
