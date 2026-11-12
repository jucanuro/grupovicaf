"""Permiso correo.administrar: crear cuentas de correo y dar o quitar accesos.

Se da a los roles de Administración y Gerencia (igual que correo.ver). Ver
correo.administracion. El superusuario siempre puede.
"""
import unicodedata

from django.db import migrations


def _sin_tildes(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in texto if not unicodedata.combining(c)).lower()


def forwards(apps, schema_editor):
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    RolTrabajador = apps.get_model('trabajadores', 'RolTrabajador')

    modulo, _ = ModuloSistema.objects.get_or_create(
        codigo='correo', defaults={'nombre': 'Correo', 'orden': 30, 'activo': True},
    )
    # Si alguien ya creó la acción «Administrar» a mano (nombre único), se reutiliza.
    accion = (AccionPermiso.objects.filter(codigo='administrar').first()
              or AccionPermiso.objects.filter(nombre__iexact='Administrar').first()
              or AccionPermiso.objects.create(codigo='administrar', nombre='Administrar', orden=9, activo=True))
    permiso, _ = PermisoModulo.objects.get_or_create(
        modulo_sistema=modulo, accion=accion,
        defaults={
            'codigo': 'correo.administrar',
            'nombre': f'{accion.nombre} {modulo.nombre}',
            'descripcion': 'Crea cuentas de correo y decide quién puede abrir cada una.',
        },
    )
    for rol in RolTrabajador.objects.all():
        nombre = _sin_tildes(rol.nombre)
        if 'admin' in nombre or 'gerent' in nombre or 'gerencia' in nombre:
            rol.permisos.add(permiso)


def backwards(apps, schema_editor):
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    PermisoModulo.objects.filter(codigo='correo.administrar').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('correo', '0004_bitacora_administracion'),
        ('trabajadores', '0007_permiso_ensayos_ver_todos'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
