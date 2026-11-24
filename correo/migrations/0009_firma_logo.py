from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('correo', '0008_firma_plantilla')]

    operations = [
        migrations.AddField(
            model_name='firma',
            name='logo',
            field=models.ImageField(
                blank=True, upload_to='correo/firmas/',
                help_text='Logo subido para la firma con plantilla (vacío = logo de Grupo VICAF). Es público: '
                          'lo cargan los clientes de correo de quien recibe el mensaje.'),
        ),
    ]
