"""Registro central de sitemaps del sitio público.

Cada app web_* registra aquí su propia clase Sitemap.
"""
from web_acreditacion.sitemaps import AcreditacionSitemap
from web_catalogo.sitemaps import CatalogoListadosSitemap, ServicioPublicadoSitemap
from web_contacto.sitemaps import ContactoSitemap
from web_inicio.sitemaps import InicioSitemap
from web_nosotros.sitemaps import NosotrosSitemap
from web_zonas.sitemaps import ZonaCoberturaSitemap, ZonasListadoSitemap

sitemaps = {
    'inicio': InicioSitemap,
    'nosotros': NosotrosSitemap,
    'acreditacion': AcreditacionSitemap,
    'servicios': ServicioPublicadoSitemap,
    'catalogo': CatalogoListadosSitemap,
    'zonas': ZonaCoberturaSitemap,
    'zonas-listado': ZonasListadoSitemap,
    'contacto': ContactoSitemap,
}
