from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('correo', '0005_permiso_correo_administrar')]

    operations = [
        migrations.CreateModel(
            name='ReglaBloqueo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('correo', 'Dirección exacta'), ('dominio', 'Dominio completo')], default='dominio', max_length=8)),
                ('valor', models.CharField(help_text='Dirección (x@y.com) o dominio (y.com), sin espacios.', max_length=254)),
                ('activa', models.BooleanField(default=True)),
                ('nota', models.CharField(blank=True, max_length=200)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'regla de bloqueo',
                'verbose_name_plural': 'reglas de bloqueo',
                'ordering': ['valor'],
            },
        ),
        migrations.AddConstraint(
            model_name='reglabloqueo',
            constraint=models.UniqueConstraint(fields=('tipo', 'valor'), name='correo_regla_bloqueo_unica'),
        ),
    ]
