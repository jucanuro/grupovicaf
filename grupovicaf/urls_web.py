from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path

from .sitemaps import sitemaps


def robots_txt(request):
    if settings.DEBUG:
        lineas = ["User-agent: *", "Disallow: /"]
    else:
        lineas = [
            "User-agent: *",
            "Disallow: /portal/",
            "Disallow: /proyectos/v/",
            "Disallow: /admin/",
            "",
            f"Sitemap: {settings.SITE_URL}/sitemap.xml",
        ]
    return HttpResponse("\n".join(lineas), content_type="text/plain")


urlpatterns = [
    path('', include('web_inicio.urls')),
    path('nosotros/', include('web_nosotros.urls', namespace='web_nosotros')),
    path('acreditacion/', include('web_acreditacion.urls', namespace='web_acreditacion')),
    path('', include('web_catalogo.urls', namespace='web_catalogo')),
    path('', include('web_zonas.urls', namespace='web_zonas')),
    path('contacto/', include('web_contacto.urls', namespace='web_contacto')),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
