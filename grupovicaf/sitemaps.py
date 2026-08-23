"""Registro central de sitemaps del sitio público.

Cada app web_* registra aquí su propia clase Sitemap.
"""
from web_acreditacion.sitemaps import AcreditacionSitemap
from web_inicio.sitemaps import InicioSitemap
from web_nosotros.sitemaps import NosotrosSitemap

sitemaps = {
    'inicio': InicioSitemap,
    'nosotros': NosotrosSitemap,
    'acreditacion': AcreditacionSitemap,
}
