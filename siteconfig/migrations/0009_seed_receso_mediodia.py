from datetime import time

from django.db import migrations


def fijar_receso(apps, schema_editor):
    """Horario aprobado por el Gerente (D-VCF-004): L-V 8:00-13:00 y 15:00-18:00,
    sáb 8:00-13:00. Solo se agrega el receso; apertura y cierre ya estaban en el seed."""
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.filter(pk=1).update(
        horario_semana_receso_inicio=time(13, 0),
        horario_semana_receso_fin=time(15, 0),
    )


def quitar_receso(apps, schema_editor):
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.filter(pk=1).update(
        horario_semana_receso_inicio=None,
        horario_semana_receso_fin=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('siteconfig', '0008_negocioconfig_receso'),
    ]

    operations = [
        migrations.RunPython(fijar_receso, quitar_receso),
    ]
