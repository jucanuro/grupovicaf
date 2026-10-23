import json

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

from ..models import Certificacion

register = template.Library()

# Mismo escape que json_script: el JSON va dentro de <script> y un "</script>"
# en un texto cargado desde el admin no debe cerrar la etiqueta.
_ESCAPES_HTML = {ord('<'): '\\u003C', ord('>'): '\\u003E', ord('&'): '\\u0026'}


@register.simple_tag
def certificaciones_jsonld():
    """Lista JSON de Certification para LocalBusiness.hasCertification (REQ-WEB-38).

    Devuelve '' si no hay ninguna publicada (RN-15), para que base.html omita la
    propiedad entera.
    """
    certificaciones = Certificacion.objects.publicadas().only(
        'norma', 'sistema', 'numero_certificado', 'organismo', 'fecha_emision',
        'vigencia_hasta', 'archivo',
    )
    sitio = settings.SITE_URL.rstrip('/')
    datos = []
    for cert in certificaciones:
        item = {
            '@type': 'Certification',
            'name': f'{cert.norma} · {cert.sistema}' if cert.sistema else cert.norma,
            'certificationIdentification': cert.numero_certificado,
            'issuedBy': {'@type': 'Organization', 'name': cert.organismo},
            'expires': cert.vigencia_hasta.isoformat(),
            'certificationStatus': 'https://schema.org/CertificationActive',
            'url': f'{sitio}{cert.archivo.url}',
        }
        if cert.fecha_emision:
            item['validFrom'] = cert.fecha_emision.isoformat()
        datos.append(item)
    if not datos:
        return ''
    return mark_safe(json.dumps(datos, ensure_ascii=False).translate(_ESCAPES_HTML))
