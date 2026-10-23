from django.db import migrations

# specs/WEB v4 (T20, REQ-WEB-52): la descripción del negocio es la meta
# description de la home y de las páginas sin una propia, y decía "cobertura en
# el norte del Perú". El laboratorio opera solo en Cajamarca (D-VCF-002).
ANTES = (
    'Laboratorio de ensayo de materiales y geotecnia acreditado por '
    'INACAL, con sede en Cajamarca y cobertura en el norte del Perú.'
)
DESPUES = (
    'Laboratorio de ensayo de materiales y geotecnia acreditado por '
    'INACAL, con sede en Cajamarca.'
)


def solo_cajamarca(apps, schema_editor):
    # Solo si sigue el texto de la semilla: no pisa lo que se haya editado en el admin.
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.filter(descripcion=ANTES).update(descripcion=DESPUES)


def restaurar(apps, schema_editor):
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.filter(descripcion=DESPUES).update(descripcion=ANTES)


class Migration(migrations.Migration):

    dependencies = [
        ('siteconfig', '0007_seed_ensayos_acreditados'),
    ]

    operations = [
        migrations.RunPython(solo_cajamarca, restaurar),
    ]
