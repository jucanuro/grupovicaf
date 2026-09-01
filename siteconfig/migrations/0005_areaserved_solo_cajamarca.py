from django.db import migrations


def solo_cajamarca(apps, schema_editor):
    """El laboratorio opera solo en Cajamarca: areaServed deja de listar las
    provincias del norte (eran keywords de landings de cobertura que ya no
    existen — ver eliminación de web_zonas)."""
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.filter(pk=1).update(ciudades_cobertura=['Cajamarca'])


def restaurar_norte(apps, schema_editor):
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.filter(pk=1).update(
        ciudades_cobertura=[
            'Cajamarca', 'Jaén', 'Chota', 'Celendín', 'Bambamarca', 'Cajabamba', 'Cutervo',
        ]
    )


class Migration(migrations.Migration):

    dependencies = [
        ('siteconfig', '0004_negocioconfig_ruc'),
    ]

    operations = [
        migrations.RunPython(solo_cajamarca, restaurar_norte),
    ]
