from django.db import migrations


def crear(apps, schema_editor):
    # unaccent es una extensión "trusted" desde PostgreSQL 13: la crea el
    # dueño de la base sin superusuario. En sqlite (dev sin Docker) no aplica.
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('CREATE EXTENSION IF NOT EXISTS unaccent')


def quitar(apps, schema_editor):
    # No se borra: otra app podría usarla. Revertir esta migración es seguro.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('correo', '0002_modelos_correo'),
    ]

    operations = [
        migrations.RunPython(crear, quitar),
    ]
