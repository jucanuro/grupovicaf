"""QR de verificación de la cotización (como el del informe)."""
import base64
import io

from django.conf import settings
from django.urls import reverse


def url_verificacion(cotizacion):
    """Página pública mínima: solo confirma el número y la fecha; nunca muestra montos, RUC ni cliente."""
    return f"{settings.SITE_URL.rstrip('/')}{reverse('servicios:verificar_cotizacion', args=[cotizacion.numero_oferta])}"


def qr_data_uri(texto):
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(texto)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color='black', back_color='white').save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
