from django.db import migrations

PERMISOS = [
    ('aprobar', 'Aprobar', 'Revisa, devuelve o aprueba las probetas y emite el informe de compresión.'),
    ('exportar', 'Exportar', 'Descarga a Excel los datos de los ensayos de compresión.'),
]


def forwards(apps, schema_editor):
    """Asegura informes.aprobar e informes.exportar (HU-LIMS-15 y 18;
    DP-LIMS-16 A) y los da a los roles que ya pueden crear informes. Se
    ajustan luego desde Administración > Roles."""
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')
    RolTrabajador = apps.get_model('trabajadores', 'RolTrabajador')

    modulo, _ = ModuloSistema.objects.get_or_create(
        codigo='informes', defaults={'nombre': 'Informes', 'orden': 11, 'activo': True},
    )
    for orden, (codigo, nombre, descripcion) in enumerate(PERMISOS, start=6):
        accion = AccionPermiso.objects.filter(codigo=codigo).first() or AccionPermiso.objects.filter(nombre=nombre).first()
        if accion is None:
            accion = AccionPermiso.objects.create(codigo=codigo, nombre=nombre, orden=orden, activo=True)
        permiso = PermisoModulo.objects.filter(codigo=f'informes.{codigo}').first()
        if permiso is None:
            permiso, _ = PermisoModulo.objects.get_or_create(
                modulo_sistema=modulo, accion=accion,
                defaults={'codigo': f'informes.{codigo}', 'nombre': f'{accion.nombre} {modulo.nombre}',
                          'descripcion': descripcion},
            )
        for rol in RolTrabajador.objects.filter(permisos__codigo='informes.crear').distinct():
            rol.permisos.add(permiso)


def backwards(apps, schema_editor):
    pass  # Los permisos pudieron existir antes; no se borran.


class Migration(migrations.Migration):

    dependencies = [
        ('trabajadores', '0010_permisos_equipos'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
