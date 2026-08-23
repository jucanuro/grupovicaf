from django.shortcuts import render

from .models import CarruselInicio


def inicio_view(request):
    slides = CarruselInicio.objects.vigentes().only(
        'id', 'titulo', 'descripcion', 'imagen', 'alt_text', 'enlace', 'orden',
    )
    return render(request, 'web/home.html', {'slides': slides})
