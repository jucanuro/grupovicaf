"""Bandeja de solicitudes de cotización que llegan desde la web pública.

El formulario de /contacto/ solo guarda la SolicitudCotizacionWeb. Aquí el
laboratorio la revisa y decide: convertirla en Cotizacion (recién entonces se
asigna el número VCF-OTE y se crea o reutiliza el Cliente por RUC) o
descartarla si es spam o un duplicado.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clientes.models import Cliente
from trabajadores.permissions import permiso_requerido
from web_contacto.models import SolicitudCotizacionItem, SolicitudCotizacionWeb
from web_contacto.services import procesar_solicitud_cotizacion


@login_required
@permiso_requerido('cotizaciones.ver')
def lista_solicitudes_web(request):
    ver = request.GET.get('ver', 'pendientes')
    solicitudes = (
        SolicitudCotizacionWeb.objects.select_related('cotizacion', 'cliente')
        .prefetch_related(
            Prefetch(
                'items',
                queryset=SolicitudCotizacionItem.objects.select_related('servicio_publicado'),
            )
        )
        .order_by('-creado')
    )
    if ver == 'convertidas':
        solicitudes = solicitudes.filter(cotizacion__isnull=False)
    else:
        ver = 'pendientes'
        solicitudes = solicitudes.filter(cotizacion__isnull=True)

    page_obj = Paginator(solicitudes, 20).get_page(request.GET.get('page'))

    # Avisar si el RUC ya es de un cliente registrado: al convertir, la
    # cotización se cuelga de ese cliente y hay que confirmar que es él.
    rucs = {s.ruc for s in page_obj}
    clientes_por_ruc = dict(
        Cliente.objects.filter(ruc__in=rucs).values_list('ruc', 'razon_social')
    )
    for solicitud in page_obj:
        solicitud.cliente_existente = clientes_por_ruc.get(solicitud.ruc)

    return render(request, 'servicios/solicitudes_web_list.html', {
        'solicitudes': page_obj,
        'ver': ver,
        'total_pendientes': SolicitudCotizacionWeb.objects.filter(cotizacion__isnull=True).count(),
    })


@require_POST
@login_required
@permiso_requerido('cotizaciones.crear')
def convertir_solicitud_web(request, pk):
    solicitud = get_object_or_404(SolicitudCotizacionWeb, pk=pk)
    if solicitud.cotizacion_id:
        messages.info(request, f'La solicitud ya se convirtió en {solicitud.cotizacion.numero_oferta}.')
        return redirect('servicios:editar_cotizacion', pk=solicitud.cotizacion_id)

    cotizacion = procesar_solicitud_cotizacion(solicitud)
    messages.success(
        request,
        f'Se creó la cotización {cotizacion.numero_oferta} desde la solicitud web de '
        f'{solicitud.razon_social}. Revisa precios, condiciones y envíala al cliente.',
    )
    return redirect('servicios:editar_cotizacion', pk=cotizacion.pk)


@require_POST
@login_required
@permiso_requerido('cotizaciones.eliminar')
def descartar_solicitud_web(request, pk):
    solicitud = get_object_or_404(SolicitudCotizacionWeb, pk=pk, cotizacion__isnull=True)
    razon_social = solicitud.razon_social
    solicitud.delete()
    messages.success(request, f'Se descartó la solicitud web de {razon_social}.')
    return redirect('servicios:lista_solicitudes_web')
