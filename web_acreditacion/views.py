from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.static import serve

from servicios.models import Servicio

from .models import Acreditacion, Certificacion


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
    # RN-15: solo activas, con PDF y vigentes en la fecha de Lima. Lista blanca de campos.
    certificaciones = Certificacion.objects.publicadas().only(
        'id', 'norma', 'sistema', 'numero_certificado', 'organismo', 'alcance', 'sede',
        'fecha_emision', 'vigencia_hasta', 'archivo', 'sello', 'sello_alt',
    )
    return render(request, 'web/acreditacion.html', {
        'acreditaciones': acreditaciones,
        'certificaciones': certificaciones,
    })


@xframe_options_sameorigin
def servir_certificado_dev(request, path):
    """Sirve /media/certificaciones/ en dev con X-Frame-Options SAMEORIGIN (REQ-WEB-37).

    El static() genérico de urls_web.py pasa por XFrameOptionsMiddleware (DENY)
    y el modal de /acreditacion/ no podría embeber el PDF. Solo se enruta con
    DEBUG; en producción lo sirve nginx (deploy/nginx/grupovicaf.conf).
    """
    return serve(request, f'certificaciones/{path}', document_root=settings.MEDIA_ROOT)
