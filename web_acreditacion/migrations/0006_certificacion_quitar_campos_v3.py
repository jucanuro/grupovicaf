# specs/WEB v4 (T18), paso 3 de 3: quita los campos de la tarjeta ISO 9001 de v3.
# La 0005 ya pasó su contenido a título y descripción.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('web_acreditacion', '0005_certificaciones_inacal_e_iso9001'),
    ]

    operations = [
        migrations.RemoveField(model_name='certificacion', name='norma'),
        migrations.RemoveField(model_name='certificacion', name='sistema'),
        migrations.RemoveField(model_name='certificacion', name='numero_certificado'),
        migrations.RemoveField(model_name='certificacion', name='organismo'),
        migrations.RemoveField(model_name='certificacion', name='alcance'),
        migrations.RemoveField(model_name='certificacion', name='sede'),
        migrations.RemoveField(model_name='certificacion', name='fecha_emision'),
        migrations.RemoveField(model_name='certificacion', name='sello'),
        migrations.RemoveField(model_name='certificacion', name='sello_alt'),
    ]
