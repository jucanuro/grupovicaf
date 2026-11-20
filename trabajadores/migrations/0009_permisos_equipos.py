from django.db import migrations

PERMISOS = [
    ('ver', 'Ver', 'Consulta los equipos del laboratorio y su calibración.'),
    ('editar', 'Editar', 'Registra equipos y actualiza sus datos de calibración.'),
]


def forwards(apps, schema_editor):
    """Crea equipos.ver y equipos.editar (HU-LIMS-12) y se los da a los roles
    que hoy ven todos los ensayos (supervisión). Se ajusta luego desde
    Administración > Roles.
    """
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    RolTrabajador = apps.get_model('trabajadores', 'RolTrabajador')

    modulo, _ = ModuloSistema.objects.get_or_create(
        codigo='equipos', defaults={'nombre': 'Equipos', 'orden': 11, 'activo': True, 'icono': 'gauge'},
    )
    nuevos = []
    for orden, (codigo, nombre, descripcion) in enumerate(PERMISOS, start=1):
        accion = AccionPermiso.objects.filter(codigo=codigo).first()
        if accion is None:
            accion = AccionPermiso.objects.filter(nombre=nombre).first()
        if accion is None:
            accion = AccionPermiso.objects.create(codigo=codigo, nombre=nombre, orden=orden, activo=True)
        permiso, _ = PermisoModulo.objects.get_or_create(
            modulo_sistema=modulo, accion=accion,
            defaults={
                'codigo': f'equipos.{accion.codigo}',
                'nombre': f'{accion.nombre} {modulo.nombre}',
                'descripcion': descripcion,
            },
        )
        nuevos.append(permiso)

    for rol in RolTrabajador.objects.filter(permisos__codigo='ensayos.ver_todos').distinct():
        rol.permisos.add(*nuevos)


def backwards(apps, schema_editor):
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    PermisoModulo.objects.filter(codigo__in=['equipos.ver', 'equipos.editar']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('trabajadores', '0008_permiso_ensayos_registrar'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
