from django.shortcuts import render

from .models import Nosotros
from .services import obtener_documentos_nosotros


def nosotros_view(request):
    nosotros = Nosotros.objects.only(
        'titulo', 'contenido', 'imagen', 'imagen_alt',
        'meta_title', 'meta_description', 'noindex', 'imagen_og',
    ).first()

    context = {'nosotros': nosotros, **obtener_documentos_nosotros()}
    return render(request, 'web/nosotros.html', context)
