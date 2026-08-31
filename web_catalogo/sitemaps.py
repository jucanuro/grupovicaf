from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import ClienteDestacado, LineaServicio, MiembroEquipoPublicado, ServicioPublicado


class LineaServicioSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return LineaServicio.objects.publicadas().only('slug', 'actualizado')

    def location(self, item):
        return reverse('web_catalogo:servicio_detalle', kwargs={'slug': item.slug})

    def lastmod(self, item):
        return item.actualizado


class ServicioPublicadoSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return ServicioPublicado.objects.publicados().only('slug', 'actualizado')

    def location(self, item):
        return reverse('web_catalogo:servicio_detalle', kwargs={'slug': item.slug})

    def lastmod(self, item):
        return item.actualizado


class CatalogoListadosSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return ['web_catalogo:servicios_list', 'web_catalogo:clientes_list', 'web_catalogo:equipo_list']

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        if item == 'web_catalogo:clientes_list':
            ultimo = ClienteDestacado.objects.filter(activo=True).only('actualizado').order_by('-actualizado').first()
        elif item == 'web_catalogo:equipo_list':
            ultimo = MiembroEquipoPublicado.objects.filter(activo=True).only('actualizado').order_by('-actualizado').first()
        else:
            ultimo = LineaServicio.objects.publicadas().only('actualizado').order_by('-actualizado').first()
        return ultimo.actualizado if ultimo else None
