import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


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
