from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('correo', '0010_cuenta_personal')]

    operations = [
        migrations.CreateModel(
            name='ReglaPermitido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('correo', 'Dirección exacta'), ('dominio', 'Dominio completo')], default='dominio', max_length=8)),
                ('valor', models.CharField(help_text='Dirección (x@y.com) o dominio (y.com), sin espacios.', max_length=254)),
                ('activa', models.BooleanField(default=True)),
                ('nota', models.CharField(blank=True, max_length=200)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'remitente de confianza', 'verbose_name_plural': 'remitentes de confianza', 'ordering': ['valor']},
        ),
        migrations.AddConstraint(
            model_name='reglapermitido',
            constraint=models.UniqueConstraint(fields=('tipo', 'valor'), name='correo_regla_permitido_unica'),
        ),
    ]
