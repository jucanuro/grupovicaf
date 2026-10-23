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
    """Lista JSON de Certification para LocalBusiness.hasCertification (REQ-WEB-51).

    Solo tipos ISO y Otro: la acreditación INACAL ya va como hasCredential en
    base.html. Devuelve '' si no hay ninguna publicada (RN-15), para que
    base.html omita la propiedad entera.
    """
    certificaciones = (
        Certificacion.objects.publicadas()
        .exclude(tipo=Certificacion.TIPO_ACREDITACION)
        .only('titulo', 'descripcion', 'institucion', 'vigencia_hasta', 'archivo')
    )
    sitio = settings.SITE_URL.rstrip('/')
    datos = []
    for cert in certificaciones:
        item = {
            '@type': 'Certification',
            'name': cert.titulo,
            'description': cert.descripcion,
            'issuedBy': {'@type': 'Organization', 'name': cert.institucion},
            'certificationStatus': 'https://schema.org/CertificationActive',
            'url': f'{sitio}{cert.archivo.url}',
        }
        if cert.vigencia_hasta:
            item['expires'] = cert.vigencia_hasta.isoformat()
        datos.append(item)
    if not datos:
        return ''
    return mark_safe(json.dumps(datos, ensure_ascii=False).translate(_ESCAPES_HTML))
