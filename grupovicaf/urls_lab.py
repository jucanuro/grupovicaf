from django.contrib import admin
from django.urls import path,include

from django.conf import settings
from django.conf.urls.static import static

from correo import views as correo_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('inicio/', correo_views.inicio, name='inicio'),
    path('correo/', include('correo.urls_lab', namespace='correo')),
    path('clientes/', include('clientes.urls', namespace='clientes')),
    path('trabajadores/', include('trabajadores.urls', namespace='trabajadores')),
    path('servicios/', include('servicios.urls', namespace='servicios')),
    path('proyectos/', include('proyectos.urls',namespace='proyectos')),
    path('actividades/', include('actividades.urls',namespace='actividades')),
    path('analisis/', include('analisis.urls', namespace='analisis')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
