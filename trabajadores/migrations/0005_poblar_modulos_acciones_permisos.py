from django.db import migrations
from django.utils.text import slugify


MODULOS_BASE = [
    'Administración',
    'Dashboard',
    'Clientes',
    'Trabajadores',
    'Roles',
    'Servicios',
    'Cotizaciones',
    'Proyectos',
    'Muestras',
    'Ensayos',
    'Informes',
    'Calendario',
    'Gantt',
]


ACCIONES_BASE = [
    'Ver',
    'Crear',
    'Editar',
    'Eliminar',
    'Exportar',
    'Aprobar',
    'Firmar',
]


def forwards(apps, schema_editor):
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')
    PermisoModulo = apps.get_model('trabajadores', 'PermisoModulo')

    for index, nombre in enumerate(MODULOS_BASE, start=1):
        ModuloSistema.objects.get_or_create(
            codigo=slugify(nombre).replace('-', '_'),
            defaults={
                'nombre': nombre,
                'orden': index,
                'activo': True,
            }
        )

    for index, nombre in enumerate(ACCIONES_BASE, start=1):
        AccionPermiso.objects.get_or_create(
            codigo=slugify(nombre).replace('-', '_'),
            defaults={
                'nombre': nombre,
                'orden': index,
                'activo': True,
            }
        )

    for permiso in PermisoModulo.objects.all():
        partes = permiso.codigo.split('.')

        if len(partes) != 2:
            continue

        modulo_codigo = partes[0].strip().lower()
        accion_codigo = partes[1].strip().lower()

        modulo = ModuloSistema.objects.filter(codigo=modulo_codigo).first()
        accion = AccionPermiso.objects.filter(codigo=accion_codigo).first()

        if modulo and accion:
            permiso.modulo_sistema = modulo
            permiso.accion = accion
            permiso.save(update_fields=['modulo_sistema', 'accion'])


def backwards(apps, schema_editor):
    ModuloSistema = apps.get_model('trabajadores', 'ModuloSistema')
    AccionPermiso = apps.get_model('trabajadores', 'AccionPermiso')

    ModuloSistema.objects.all().delete()
    AccionPermiso.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('trabajadores', '0004_accionpermiso_modulosistema_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]