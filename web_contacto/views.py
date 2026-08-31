from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from web_catalogo.models import ServicioPublicado
from web_zonas.models import ZonaCobertura

from .models import MensajeContacto, SolicitudCotizacionItem, SolicitudCotizacionWeb
from .services import procesar_solicitud_cotizacion
from .tasks import enviar_correo_mensaje_contacto, enviar_correo_solicitud_cotizacion
from .utils import es_honeypot, obtener_ip_cliente, rate_limit_excedido


def contacto_view(request):
    """/contacto/ — mensaje simple + solicitud de cotización (POST via solicitud_cotizacion_view)."""
    if request.method == 'POST':
        return _procesar_mensaje(request)

    servicios_disponibles = (
        ServicioPublicado.objects.publicados()
        .filter(servicio__isnull=False)
        .select_related('categoria')
        .only('slug', 'titulo_publico', 'categoria__nombre', 'linea__slug', 'linea_id')
        .order_by('categoria__nombre', 'titulo_publico')
    )
    zonas = ZonaCobertura.objects.activas().only('slug', 'nombre')
    origen_sugerido = request.GET.get('origen') or request.META.get('HTTP_REFERER', '') or request.path

    context = {
        'servicios_disponibles': servicios_disponibles,
        'zonas': zonas,
        'origen_sugerido': origen_sugerido[:255],
        # CTA de linea_detalle.html: ?linea=<slug> llega hasta acá y el JS de
        # contacto.html precarga los checkboxes de esa línea (ver bloque al
        # final de la plantilla). Ningún dato del cliente depende de esto.
        'linea_preseleccionada': request.GET.get('linea', '')[:100],
    }
    return render(request, 'web/contacto.html', context)


def _procesar_mensaje(request):
    if es_honeypot(request):
        # No delatamos al bot: mismo mensaje de éxito, pero no se guarda nada.
        messages.success(request, 'Gracias por escribirnos. Te responderemos pronto.')
        return redirect('web_contacto:contacto')

    if rate_limit_excedido(request, 'mensaje'):
        messages.error(request, 'Has enviado demasiados mensajes en poco tiempo. Intenta de nuevo más tarde.')
        return redirect('web_contacto:contacto')

    nombre = request.POST.get('nombre', '').strip()
    correo = request.POST.get('correo', '').strip()
    telefono = request.POST.get('telefono', '').strip()
    asunto = request.POST.get('asunto', '').strip()
    cuerpo_mensaje = request.POST.get('mensaje', '').strip()

    if not (nombre and correo and asunto and cuerpo_mensaje):
        messages.error(request, 'Completa nombre, correo, asunto y mensaje.')
        return redirect('web_contacto:contacto')

    mensaje = MensajeContacto.objects.create(
        nombre=nombre,
        correo=correo,
        telefono=telefono,
        asunto=asunto,
        mensaje=cuerpo_mensaje,
        origen=request.POST.get('origen', '')[:255],
        ip=obtener_ip_cliente(request),
    )
    enviar_correo_mensaje_contacto.delay(mensaje.pk)

    messages.success(request, 'Gracias por escribirnos. Te responderemos pronto.')
    return redirect('web_contacto:contacto')


@require_POST
def solicitud_cotizacion_view(request):
    """Crea SolicitudCotizacionWeb + ítems y dispara el flujo hacia el LIMS (web_contacto.services)."""
    if es_honeypot(request):
        messages.success(request, 'Gracias, recibimos tu solicitud. Te contactaremos pronto.')
        return redirect('web_contacto:contacto')

    if rate_limit_excedido(request, 'cotizacion'):
        messages.error(request, 'Has enviado demasiadas solicitudes en poco tiempo. Intenta de nuevo más tarde.')
        return redirect('web_contacto:contacto')

    ruc = request.POST.get('ruc', '').strip()
    razon_social = request.POST.get('razon_social', '').strip()
    persona_contacto = request.POST.get('persona_contacto', '').strip()
    correo_contacto = request.POST.get('correo_contacto', '').strip()
    telefono_contacto = request.POST.get('telefono_contacto', '').strip()
    necesidad = request.POST.get('necesidad', '').strip()
    zona_slug = request.POST.get('zona', '').strip()
    servicio_slugs = [s for s in request.POST.getlist('servicios') if s]

    errores = []
    if not (ruc.isdigit() and len(ruc) == 11):
        errores.append('El RUC debe tener 11 dígitos numéricos.')
    if not razon_social:
        errores.append('Falta la razón social.')
    if not (persona_contacto and correo_contacto and telefono_contacto):
        errores.append('Completa persona de contacto, correo y teléfono.')
    if not necesidad:
        errores.append('Describe brevemente tu necesidad.')

    servicios_publicados = list(
        ServicioPublicado.objects.publicados()
        .filter(servicio__isnull=False, slug__in=servicio_slugs)
        .select_related('servicio')
    )
    if not servicios_publicados:
        errores.append('Selecciona al menos un servicio.')

    if errores:
        for error in errores:
            messages.error(request, error)
        return redirect('web_contacto:contacto')

    zona = ZonaCobertura.objects.activas().filter(slug=zona_slug).first() if zona_slug else None

    with transaction.atomic():
        solicitud = SolicitudCotizacionWeb.objects.create(
            ruc=ruc,
            razon_social=razon_social,
            persona_contacto=persona_contacto,
            correo_contacto=correo_contacto,
            telefono_contacto=telefono_contacto,
            zona=zona,
            necesidad=necesidad,
            origen=request.POST.get('origen', '')[:255],
            ip=obtener_ip_cliente(request),
        )

        for sp in servicios_publicados:
            try:
                cantidad = max(1, int(request.POST.get(f'cantidad_{sp.slug}', '1')))
            except ValueError:
                cantidad = 1
            SolicitudCotizacionItem.objects.create(
                solicitud=solicitud,
                servicio_publicado=sp,
                cantidad_estimada=cantidad,
            )

        cotizacion = procesar_solicitud_cotizacion(solicitud)

    enviar_correo_solicitud_cotizacion.delay(solicitud.pk, cotizacion.pk)

    messages.success(
        request, 'Gracias, recibimos tu solicitud de cotización. Nuestro equipo te contactará pronto.',
    )
    return redirect('web_contacto:contacto')
