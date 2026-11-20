from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('correo', '0006_regla_bloqueo')]

    operations = [
        migrations.AddField(
            model_name='mensaje',
            name='sin_verificar',
            field=models.BooleanField(
                default=False, help_text='Remitente externo sin firma DKIM: se muestra un aviso al leerlo.'),
        ),
    ]
