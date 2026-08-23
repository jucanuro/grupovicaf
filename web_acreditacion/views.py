from django.db.models import Prefetch
from django.shortcuts import render

from servicios.models import Servicio

from .models import Acreditacion


def acreditacion_view(request):
    servicios_qs = (
        Servicio.objects.only(
            'id', 'nombre', 'codigo_facturacion', 'esta_acreditado',
            'publicado__slug', 'publicado__activo',
        )
        .select_related('publicado')
    )
    acreditaciones = (
        Acreditacion.objects.filter(activo=True)
        .prefetch_related(Prefetch('servicios_acreditados', queryset=servicios_qs))
        .order_by('orden', '-vigencia_desde')
    )
    return render(request, 'web/acreditacion.html', {'acreditaciones': acreditaciones})
