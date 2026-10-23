# specs/WEB v4 (T18), paso 1 de 3: campos de la card. Se agregan con default
# para que la 0005 los llene desde los campos de v3 antes de que la 0006 los quite.

import django.core.validators
from django.db import migrations, models
import web_acreditacion.models


class Migration(migrations.Migration):

    dependencies = [
        ('web_acreditacion', '0003_seed_certificado_iso9001'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='certificacion',
            options={'ordering': ['orden', 'titulo'], 'verbose_name': 'Certificación', 'verbose_name_plural': 'Certificaciones'},
        ),
        migrations.AddField(
            model_name='certificacion',
            name='titulo',
            field=models.CharField(default='', help_text='Ej.: Acreditación INACAL LE-230', max_length=120, verbose_name='Título'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='certificacion',
            name='descripcion',
            field=models.CharField(default='', help_text='Una o dos frases; la card muestra hasta 3 líneas.', max_length=200, verbose_name='Descripción corta'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='certificacion',
            name='tipo',
            field=models.CharField(choices=[('acreditacion', 'Acreditación'), ('iso', 'Certificación ISO'), ('otro', 'Otro')], default='otro', max_length=20),
        ),
        migrations.AddField(
            model_name='certificacion',
            name='institucion',
            field=models.CharField(default='', help_text='Ej.: Instituto Nacional de Calidad (INACAL)', max_length=150, verbose_name='Institución que la otorga'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='certificacion',
            name='vigencia_hasta',
            field=models.DateField(blank=True, help_text='Opcional. Desde el día siguiente la certificación deja de mostrarse en la web.', null=True, verbose_name='Vigente hasta'),
        ),
        migrations.AlterField(
            model_name='certificacion',
            name='archivo',
            field=models.FileField(help_text='JPG, PNG, WebP o PDF, máximo 10 MB. En móvil el PDF se abre en una pestaña nueva.', upload_to='certificaciones/', validators=[django.core.validators.FileExtensionValidator(('pdf', 'jpg', 'jpeg', 'png', 'webp')), web_acreditacion.models.validar_archivo], verbose_name='Archivo (imagen o PDF)'),
        ),
    ]
