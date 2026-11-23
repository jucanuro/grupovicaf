from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('correo', '0007_mensaje_sin_verificar')]

    operations = [
        migrations.AddField(
            model_name='firma',
            name='plantilla',
            field=models.JSONField(
                blank=True, null=True,
                help_text='Datos de la firma con plantilla (nombre, cargo, teléfono…); vacío = firma libre.'),
        ),
    ]
