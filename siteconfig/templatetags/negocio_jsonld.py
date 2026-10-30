from django import template
from django.conf import settings
from django.templatetags.static import static

from web_acreditacion.templatetags.certificaciones import certificaciones_schema, json_para_script

register = template.Library()

_DIAS_SEMANA = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']


def _horarios(negocio):
    tramos = [(_DIAS_SEMANA, apertura, cierre) for apertura, cierre in negocio.tramos_semana()]
    tramos += [(['Saturday'], apertura, cierre) for apertura, cierre in negocio.tramos_sabado()]
    return [
        {
            '@type': 'OpeningHoursSpecification',
            'dayOfWeek': dias,
            'opens': apertura.strftime('%H:%M'),
            'closes': cierre.strftime('%H:%M'),
        }
        for dias, apertura, cierre in tramos
    ]


@register.simple_tag
def local_business_jsonld(negocio):
    """LocalBusiness global (regla 13) armado en Python y serializado con json.dumps.

    Antes se escribía a mano en base.html con el escape de HTML: una comilla o
    un "&" cargados desde el admin rompían el JSON-LD de todas las páginas.
    NAP desde NegocioConfig (regla 14).
    """
    sitio = settings.SITE_URL.rstrip('/')
    datos = {
        '@context': 'https://schema.org',
        '@type': 'LocalBusiness',
        'name': negocio.nombre,
        'description': negocio.descripcion,
        'url': sitio,
        'image': f"{sitio}{static('web/img/LogoF.webp')}",
        'telephone': negocio.telefono,
        'email': negocio.correo,
        'address': {
            '@type': 'PostalAddress',
            'streetAddress': negocio.direccion_calle,
            'addressLocality': negocio.direccion_localidad,
            'addressRegion': negocio.direccion_region,
            'postalCode': negocio.direccion_codigo_postal,
            'addressCountry': negocio.direccion_pais,
        },
        'areaServed': list(negocio.ciudades_cobertura or []),
        'hasCredential': {
            '@type': 'EducationalOccupationalCredential',
            'credentialCategory': 'Acreditación de laboratorio de ensayo',
            'recognizedBy': {'@type': 'Organization', 'name': negocio.acreditacion_entidad},
            'identifier': negocio.acreditacion_codigo,
        },
    }
    if negocio.latitud and negocio.longitud:
        datos['geo'] = {
            '@type': 'GeoCoordinates',
            'latitude': float(negocio.latitud),
            'longitude': float(negocio.longitud),
        }
    horarios = _horarios(negocio)
    if horarios:
        datos['openingHoursSpecification'] = horarios
    certificaciones = certificaciones_schema()
    if certificaciones:
        datos['hasCertification'] = certificaciones
    return json_para_script(datos)
