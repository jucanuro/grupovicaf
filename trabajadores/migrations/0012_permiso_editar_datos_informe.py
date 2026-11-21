from django.db import migrations

CODIGO = 'informes.editar_datos'


def forwards(apps, schema_editor):
    """Permiso para convertir un bloque de datos del informe en texto editable.
    No se da a ningún rol: el Gerente lo asigna desde Administración > Roles."""
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')

    if PermisoModulo.objects.filter(codigo=CODIGO).exists():
        return
    modulo, _ = ModuloSistema.objects.get_or_create(
        codigo='informes', defaults={'nombre': 'Informes', 'orden': 11, 'activo': True},
    )
    accion = AccionPermiso.objects.filter(codigo='editar_datos').first()
    if accion is None:
        accion = AccionPermiso.objects.create(codigo='editar_datos', nombre='Editar datos del sistema', orden=8, activo=True)
    PermisoModulo.objects.get_or_create(
        modulo_sistema=modulo, accion=accion,
        defaults={
            'codigo': CODIGO,
            'nombre': 'Editar datos del sistema en Informes',
            'descripcion': 'Convierte un bloque de datos del informe (carátula, resultados, equipos o notas) '
                           'en texto editable para corregirlo a mano. Queda en el historial.',
        },
    )


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('trabajadores', '0011_permisos_informes_compresion'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
