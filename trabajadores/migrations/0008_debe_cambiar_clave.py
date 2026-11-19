from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('trabajadores', '0007_permiso_ensayos_ver_todos')]

    operations = [
        migrations.AddField(
            model_name='trabajadorprofile',
            name='debe_cambiar_clave',
            field=models.BooleanField(
                default=False, verbose_name='Debe cambiar su contraseña',
                help_text='Se activa con una contraseña temporal: al entrar, el sistema le pide cambiarla.'),
        ),
    ]
