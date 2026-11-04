import unicodedata

from django.db import migrations


def _sin_tildes(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn'
    )


def forwards(apps, schema_editor):
    """Crea reportes.ver (DP-LIMS-08 A) y se lo da a los roles de
    Administración y Gerencia. El resto se asigna desde Administración > Roles.
    """
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    RolTrabajador = apps.get_model('trabajadores', 'RolTrabajador')

    modulo, _ = ModuloSistema.objects.get_or_create(
        codigo='reportes', defaults={'nombre': 'Reportes', 'orden': 20, 'activo': True},
    )
    accion, _ = AccionPermiso.objects.get_or_create(
        codigo='ver', defaults={'nombre': 'Ver', 'orden': 1, 'activo': True},
    )
    permiso, _ = PermisoModulo.objects.get_or_create(
        modulo_sistema=modulo, accion=accion,
        defaults={
            'codigo': 'reportes.ver',
            'nombre': f'{accion.nombre} {modulo.nombre}',
            'descripcion': 'Abre Análisis (tabla dinámica). Cada conjunto de datos exige '
                           'además el permiso de ver de su módulo.',
        },
    )
    for rol in RolTrabajador.objects.all():
        nombre = _sin_tildes(rol.nombre)
        if 'admin' in nombre or 'gerent' in nombre or 'gerencia' in nombre:
            rol.permisos.add(permiso)


def backwards(apps, schema_editor):
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    PermisoModulo.objects.filter(codigo='reportes.ver').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('analisis', '0001_initial'),
        ('trabajadores', '0007_permiso_ensayos_ver_todos'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
