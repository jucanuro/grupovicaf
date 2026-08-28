from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from web_catalogo.models import ServicioPublicado

from .models import ZonaCobertura


def zonas_list_view(request):
    """/zonas/ — índice de cobertura. Sin caché: 7 filas, coste despreciable."""
    zonas = (
        ZonaCobertura.objects.activas()
        .only('slug', 'nombre', 'provincia', 'titulo_h1', 'introduccion', 'es_sede', 'orden')
    )
    return render(request, 'web/zonas_list.html', {'zonas': zonas})


def zona_detalle_view(request, slug):
    """/zonas/<slug>/ — landing de intención local con servicios disponibles."""
    zona = get_object_or_404(
        ZonaCobertura.objects.activas()
        .prefetch_related(
            Prefetch(
                'servicios',
                queryset=(
                    ServicioPublicado.objects.publicados()
                    .select_related('categoria')
                    .only('slug', 'titulo_publico', 'resumen', 'imagen', 'imagen_alt', 'categoria__nombre')
                ),
            )
        )
        .only(
            'slug', 'nombre', 'provincia', 'departamento', 'titulo_h1', 'introduccion', 'contenido',
            'latitud', 'longitud', 'es_sede',
            'meta_title', 'meta_description', 'noindex', 'imagen_og',
        ),
        slug=slug,
    )
    return render(request, 'web/zona_detalle.html', {'zona': zona})
