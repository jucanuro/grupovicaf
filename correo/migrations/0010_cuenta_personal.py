from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('correo', '0009_firma_logo')]

    operations = [
        migrations.AddField(
            model_name='cuentacorreo',
            name='personal',
            field=models.BooleanField(
                default=False, verbose_name='buzón personal',
                help_text='Buzón de una sola persona (juan@…). Se muestra arriba, aparte de los compartidos (informes@…).'),
        ),
    ]
