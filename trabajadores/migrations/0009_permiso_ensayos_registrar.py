from django.db import migrations


def forwards(apps, schema_editor):
    """Crea ensayos.registrar (registrar datos y fotos del ensayo de compresión,
    HU-LIMS-14) y se lo da a todos los roles que hoy ven ensayos, incluido el
    técnico, que es quien lo usa. Se ajusta luego desde Administración > Roles.
    """
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    RolTrabajador = apps.get_model('trabajadores', 'RolTrabajador')

    modulo, _ = ModuloSistema.objects.get_or_create(
        codigo='ensayos', defaults={'nombre': 'Ensayos', 'orden': 10, 'activo': True},
    )
    accion, _ = AccionPermiso.objects.get_or_create(
        codigo='registrar', defaults={'nombre': 'Registrar', 'orden': 9, 'activo': True},
    )
    permiso, _ = PermisoModulo.objects.get_or_create(
        modulo_sistema=modulo, accion=accion,
        defaults={
            'codigo': 'ensayos.registrar',
            'nombre': f'{accion.nombre} {modulo.nombre}',
            'descripcion': 'Registra los datos y las fotos del ensayo de compresión '
                           'de las probetas asignadas (o de todas, con Ver todos).',
        },
    )

    for rol in RolTrabajador.objects.filter(permisos__codigo='ensayos.ver').distinct():
        rol.permisos.add(permiso)


def backwards(apps, schema_editor):
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    PermisoModulo.objects.filter(codigo='ensayos.registrar').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('trabajadores', '0008_debe_cambiar_clave'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
