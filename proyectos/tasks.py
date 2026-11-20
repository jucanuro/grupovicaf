import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

ESTADOS_CERRADOS = ('FINALIZADO', 'CANCELADO')


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def procesar_informe_final(self, informe_id):
    """
    Estampa el QR de validación sobre el PDF del InformeFinal y notifica al
    responsable de firma. Se dispara tras guardar el informe: el estampado
    reescribe el PDF completo con pypdf y es lo que congelaba la pantalla
    varios segundos en `gestionar_informe_final`.
    """
    from .models import InformeFinal

    try:
        informe = InformeFinal.objects.select_related(
            'responsable_firma', 'solicitud'
        ).get(pk=informe_id)
    except InformeFinal.DoesNotExist:
        logger.warning("InformeFinal %s ya no existe; se omite el procesamiento.", informe_id)
        return

    try:
        informe.estampar_qr_en_pdf()
    except Exception as exc:
        logger.exception("Fallo al estampar el QR del informe %s", informe.codigo_informe)
        raise self.retry(exc=exc)

    _notificar_responsable(informe)


def _notificar_responsable(informe):
    responsable = informe.responsable_firma
    destinatario = responsable.correo_contacto

    if not destinatario:
        logger.warning(
            "Responsable %s sin correo_contacto; no se notifica el informe %s.",
            responsable, informe.codigo_informe,
        )
        return

    send_mail(
        subject=f"Informe {informe.codigo_informe} listo para firma",
        message=(
            f"Hola {responsable.get_nombre_formal()},\n\n"
            f"El informe {informe.codigo_informe} de la solicitud "
            f"{informe.solicitud.codigo_solicitud} ya fue procesado (QR de "
            "validación estampado) y está disponible en el sistema LIMS."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[destinatario],
        fail_silently=True,
    )


@shared_task
def notificar_proyectos_vencidos():
    """Barrido diario (Celery beat): proyectos cuya ``fecha_entrega_estimada`` ya
    pasó y que siguen abiertos (ni FINALIZADO ni CANCELADO).

    Manda un digest al correo del negocio (``NegocioConfig.correo``); si no hay
    configuración de negocio cae a ``DEFAULT_FROM_EMAIL``. Sin proyectos vencidos
    no envía nada. Devuelve el número de proyectos vencidos para trazabilidad.
    """
    from siteconfig.models import NegocioConfig
    from .models import Proyecto

    hoy = timezone.localdate()
    vencidos = list(
        Proyecto.objects
        .filter(fecha_entrega_estimada__isnull=False, fecha_entrega_estimada__lt=hoy)
        .exclude(estado__in=ESTADOS_CERRADOS)
        .select_related('cliente')
        .order_by('fecha_entrega_estimada')
    )

    if not vencidos:
        logger.info("Barrido de proyectos vencidos: nada pendiente.")
        return 0

    lineas = [
        f"- {p.codigo_proyecto} · {p.nombre_proyecto} · {p.cliente.razon_social} · "
        f"entrega {p.fecha_entrega_estimada:%d/%m/%Y} "
        f"({(hoy - p.fecha_entrega_estimada).days} día(s) de atraso) · "
        f"estado {p.get_estado_display()}"
        for p in vencidos
    ]
    logger.warning("Proyectos con entrega vencida sin cerrar: %s", len(vencidos))

    negocio = NegocioConfig.objects.first()
    destinatario = (negocio.correo if negocio else '') or settings.DEFAULT_FROM_EMAIL

    send_mail(
        subject=f"[GRUPO VICAF] {len(vencidos)} proyecto(s) con entrega vencida",
        message=(
            "Estos proyectos superaron su fecha de entrega estimada y siguen "
            "abiertos:\n\n" + "\n".join(lineas)
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[destinatario],
        fail_silently=True,
    )
    return len(vencidos)


# --- Informe de compresión armado por el sistema (HU-LIMS-16 y 19) ----------

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generar_informe_compresion(self, informe_id):
    """Arma el PDF del informe de compresión con WeasyPrint (carátula con el QR
    ya impreso + una página por probeta) y lo guarda en el InformeFinal."""
    from django.core.files.base import ContentFile

    from .informe_compresion import InformeIncompleto, generar_pdf
    from .models import InformeFinal

    informe = InformeFinal.objects.select_related(
        'solicitud__recepcion', 'solicitud__cotizacion__cliente', 'responsable_firma__rol',
    ).filter(pk=informe_id).first()
    if informe is None:
        logger.warning("InformeFinal %s ya no existe; no se genera el PDF.", informe_id)
        return

    try:
        contenido = generar_pdf(informe)
    except InformeIncompleto as exc:
        InformeFinal.objects.filter(pk=informe.pk).update(pdf_estado=InformeFinal.PDF_ERROR, pdf_error=str(exc)[:255])
        return
    except Exception as exc:
        logger.exception("Fallo al generar el PDF del informe %s", informe.codigo_informe)
        if self.request.retries >= self.max_retries:
            InformeFinal.objects.filter(pk=informe.pk).update(
                pdf_estado=InformeFinal.PDF_ERROR, pdf_error="No se pudo generar el PDF; revisa el registro del servidor.",
            )
            return
        raise self.retry(exc=exc)

    anterior = informe.archivo_pdf.name if informe.archivo_pdf else None
    informe.archivo_pdf.save(f"{informe.codigo_informe}.pdf", ContentFile(contenido), save=False)
    informe.pdf_estado = InformeFinal.PDF_LISTO
    informe.pdf_error = ''
    informe.save(update_fields=['archivo_pdf', 'pdf_estado', 'pdf_error'])
    if anterior and anterior != informe.archivo_pdf.name:
        informe.archivo_pdf.storage.delete(anterior)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generar_informe_editor(self, informe_id):
    """PDF del informe redactado en el editor: el HTML ya quedó congelado al emitir."""
    from django.core.files.base import ContentFile

    from .informe_editor import generar_pdf_borrador
    from .models import BorradorInforme, InformeFinal

    informe = InformeFinal.objects.filter(pk=informe_id).first()
    borrador = BorradorInforme.objects.filter(solicitud_id=getattr(informe, 'solicitud_id', None)).first()
    if informe is None or borrador is None or not borrador.html_emitido:
        logger.warning("Informe %s sin borrador emitido; no se genera el PDF.", informe_id)
        return
    try:
        contenido = generar_pdf_borrador(borrador.html_emitido)
    except Exception as exc:
        logger.exception("Fallo al generar el PDF del informe %s", informe.codigo_informe)
        if self.request.retries >= self.max_retries:
            InformeFinal.objects.filter(pk=informe.pk).update(
                pdf_estado=InformeFinal.PDF_ERROR, pdf_error="No se pudo generar el PDF; revisa el registro del servidor.",
            )
            return
        raise self.retry(exc=exc)

    anterior = informe.archivo_pdf.name if informe.archivo_pdf else None
    informe.archivo_pdf.save(f"{informe.codigo_informe}.pdf", ContentFile(contenido), save=False)
    informe.pdf_estado = InformeFinal.PDF_LISTO
    informe.pdf_error = ''
    informe.save(update_fields=['archivo_pdf', 'pdf_estado', 'pdf_error'])
    if anterior and anterior != informe.archivo_pdf.name:
        informe.archivo_pdf.storage.delete(anterior)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_informe_cliente(self, informe_id, destinatario):
    """Envía el PDF al contacto del cliente con el enlace de verificación y
    marca el informe como enviado."""
    from django.core.mail import EmailMessage

    from .models import InformeFinal

    informe = InformeFinal.objects.select_related('solicitud').filter(pk=informe_id).first()
    if informe is None or not informe.archivo_pdf:
        logger.warning("Informe %s sin PDF; no se envía.", informe_id)
        return

    enlace = f"{getattr(settings, 'SITE_URL', '').rstrip('/')}/proyectos/v/{informe.slug_validacion}/"
    correo = EmailMessage(
        subject=f"Informe de ensayo {informe.codigo_informe} - Grupo VICAF",
        body=(
            "Estimado cliente:\n\n"
            f"Adjuntamos el informe de ensayo {informe.codigo_informe} correspondiente a la solicitud "
            f"{informe.solicitud.codigo_solicitud}.\n\n"
            f"Puede verificar su originalidad en: {enlace}\n\n"
            "Atentamente,\nLaboratorio de Ensayo de Materiales - Grupo VICAF SAC"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario],
    )
    with informe.archivo_pdf.open('rb') as archivo:
        correo.attach(f"Informe_{informe.codigo_informe}.pdf", archivo.read(), 'application/pdf')
    try:
        correo.send()
    except Exception as exc:
        logger.exception("Fallo al enviar el informe %s", informe.codigo_informe)
        raise self.retry(exc=exc)
    InformeFinal.objects.filter(pk=informe.pk).update(estado_envio='enviado', fecha_envio=timezone.now())
