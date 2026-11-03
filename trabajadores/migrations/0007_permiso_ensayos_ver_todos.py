import unicodedata

from django.db import migrations


def _sin_tildes(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn'
    )


def forwards(apps, schema_editor):
    """Crea ensayos.ver_todos y se lo da a los roles que hoy ven ensayos,
    salvo a los de técnico: así nadie pierde acceso al desplegar y el técnico
    pasa a ver solo lo suyo y sin nombre del cliente. Se ajusta luego desde
    Administración > Roles.
    """
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    RolTrabajador = apps.get_model('trabajadores', 'RolTrabajador')

    modulo, _ = ModuloSistema.objects.get_or_create(
        codigo='ensayos', defaults={'nombre': 'Ensayos', 'orden': 10, 'activo': True},
    )
    accion, _ = AccionPermiso.objects.get_or_create(
        codigo='ver_todos', defaults={'nombre': 'Ver todos', 'orden': 8, 'activo': True},
    )
    # PermisoModulo.save() arma codigo/nombre, pero el modelo histórico no
    # tiene métodos propios: se rellenan aquí.
    permiso, _ = PermisoModulo.objects.get_or_create(
        modulo_sistema=modulo, accion=accion,
        defaults={
            'codigo': 'ensayos.ver_todos',
            'nombre': f'{accion.nombre} {modulo.nombre}',
            'descripcion': 'Ve todas las solicitudes de ensayo y el nombre del cliente. '
                           'Sin él, solo las asignadas y con el código confidencial.',
        },
    )

    for rol in RolTrabajador.objects.filter(permisos__codigo='ensayos.ver').distinct():
        if 'tecnic' in _sin_tildes(rol.nombre):
            continue
        rol.permisos.add(permiso)


def backwards(apps, schema_editor):
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    PermisoModulo.objects.filter(codigo='ensayos.ver_todos').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('trabajadores', '0006_alter_permisomodulo_options_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
