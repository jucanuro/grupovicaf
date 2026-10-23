from datetime import date

from django.db import migrations

# Datos leídos del certificado AENOR ER-0146/2026 (el PDF es una imagen; ver
# docs/proc/VCF-WEB_HU_CU_v1.md §2.4). Sin archivo ni sello: la tarjeta no se
# muestra hasta que el administrador sube el PDF desde el admin (RN-15).
CERTIFICADO = {
    'norma': 'ISO 9001:2015',
    'sistema': 'Sistema de Gestión de la Calidad',
    'organismo': 'AENOR CONFIA S.A.U.',
    'alcance': (
        'Servicios de estudios de mecánica de suelos para proyectos de '
        'construcción e infraestructura.'
    ),
    'sede': 'Jr. Los Topacios 440, Cajamarca (Perú)',
    # [Supuesto] P-12: el PDF dice "Primera emisión: 2026-04-01"; el 06-04 es
    # la fecha en que AENOR generó el PDF.
    'fecha_emision': date(2026, 4, 1),
    'vigencia_hasta': date(2029, 4, 1),
    'orden': 0,
    'activo': True,
}


def crear(apps, schema_editor):
    Certificacion = apps.get_model('web_acreditacion', 'Certificacion')
    # get_or_create: no pisa lo que el administrador ya haya corregido.
    Certificacion.objects.get_or_create(numero_certificado='ER-0146/2026', defaults=CERTIFICADO)


def borrar(apps, schema_editor):
    Certificacion = apps.get_model('web_acreditacion', 'Certificacion')
    Certificacion.objects.filter(numero_certificado='ER-0146/2026', archivo='').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('web_acreditacion', '0002_certificacion'),
    ]

    operations = [
        migrations.RunPython(crear, borrar),
    ]
