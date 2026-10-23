from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.static import serve

from servicios.models import Servicio

from .models import Acreditacion, Certificacion, primera_acreditacion


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
    certificaciones = Certificacion.objects.publicadas().para_card()
    return render(request, 'web/acreditacion.html', {
        'acreditaciones': acreditaciones,
        'certificaciones': certificaciones,
        'certificacion_acreditacion': primera_acreditacion(certificaciones),
    })


@xframe_options_sameorigin
def servir_certificado_dev(request, path):
    """Sirve /media/certificaciones/ en dev con X-Frame-Options SAMEORIGIN (REQ-WEB-37).

    El static() genérico de urls_web.py pasa por XFrameOptionsMiddleware (DENY)
    y el modal de /acreditacion/ no podría embeber el PDF. Solo se enruta con
    DEBUG; en producción lo sirve nginx (deploy/nginx/grupovicaf.conf).
    """
    return serve(request, f'certificaciones/{path}', document_root=settings.MEDIA_ROOT)
