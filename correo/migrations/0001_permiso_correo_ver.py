import unicodedata

from django.db import migrations


def _sin_tildes(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn'
    )


def forwards(apps, schema_editor):
    """Crea correo.ver y se lo da a los roles de Administración y Gerencia.

    Sin este permiso no se muestra la tarjeta Correos en la pantalla de
    entrada ni se abre email.<dominio>. El resto se asigna desde
    Administración > Roles.
    """
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    RolTrabajador = apps.get_model('trabajadores', 'RolTrabajador')

    modulo, _ = ModuloSistema.objects.get_or_create(
        codigo='correo', defaults={'nombre': 'Correo', 'orden': 30, 'activo': True},
    )
    accion, _ = AccionPermiso.objects.get_or_create(
        codigo='ver', defaults={'nombre': 'Ver', 'orden': 1, 'activo': True},
    )
    permiso, _ = PermisoModulo.objects.get_or_create(
        modulo_sistema=modulo, accion=accion,
        defaults={
            'codigo': 'correo.ver',
            'nombre': f'{accion.nombre} {modulo.nombre}',
            'descripcion': 'Muestra la tarjeta Correos y abre el correo de las cuentas asignadas.',
        },
    )
    for rol in RolTrabajador.objects.all():
        nombre = _sin_tildes(rol.nombre)
        if 'admin' in nombre or 'gerent' in nombre or 'gerencia' in nombre:
            rol.permisos.add(permiso)


def backwards(apps, schema_editor):
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    PermisoModulo.objects.filter(codigo='correo.ver').delete()
    ModuloSistema.objects.filter(codigo='correo', permisos__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('trabajadores', '0007_permiso_ensayos_ver_todos'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
