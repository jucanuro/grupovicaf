from django.db import migrations


def fijar_seis(apps, schema_editor):
    """El cliente confirma 6 ensayos en el alcance de acreditación INACAL.
    Se fija a mano porque Servicio.esta_acreditado está mal poblado en el
    LIMS (96 de 99 servicios marcados) — ver NegocioConfig.ensayos_acreditados."""
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.filter(pk=1).update(ensayos_acreditados=6)


def vaciar(apps, schema_editor):
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.filter(pk=1).update(ensayos_acreditados=None)


class Migration(migrations.Migration):

    dependencies = [
        ('siteconfig', '0006_negocioconfig_ensayos_acreditados'),
    ]

    operations = [
        migrations.RunPython(fijar_seis, vaciar),
    ]
