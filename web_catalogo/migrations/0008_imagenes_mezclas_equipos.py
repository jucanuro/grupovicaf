from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import migrations

# "Diseño de Mezclas" y "Alquiler de Equipos" se crearon a mano en el admin
# después del seed de 0003_seed_lineas_servicio y quedaron sin imagen: la
# tarjeta caía al fallback de fondo oscuro + degradado (bug reportado:
# "cajas negras vacías"). Reutiliza las fotos ya existentes en
# static/web/img/detalleservicios/{mezclas,equipos}/ en vez de subir
# material nuevo. Mismo patrón que 0003: copia a MEDIA_ROOT porque
# LineaServicio.imagen es un ImageField gestionado por el admin.
IMAGENES = {
    'diseno-de-mezclas': {
        'ruta': Path(settings.BASE_DIR) / 'static' / 'web' / 'img' / 'detalleservicios' / 'mezclas' / 'DM-1.webp',
        'alt': 'Técnico de Grupo VICAF preparando una mezcla de concreto en laboratorio',
    },
    'alquiler-de-equipos': {
        'ruta': Path(settings.BASE_DIR) / 'static' / 'web' / 'img' / 'detalleservicios' / 'equipos' / 'EQ-1.webp',
        'alt': 'Equipo de laboratorio para ensayo de materiales disponible en alquiler',
    },
}


def poblar_imagenes(apps, schema_editor):
    LineaServicio = apps.get_model('web_catalogo', 'LineaServicio')
    for slug, datos in IMAGENES.items():
        linea = LineaServicio.objects.filter(slug=slug).first()
        if linea is None or linea.imagen or not datos['ruta'].exists():
            continue
        with open(datos['ruta'], 'rb') as archivo:
            linea.imagen.save(datos['ruta'].name, File(archivo), save=False)
        linea.imagen_alt = datos['alt']
        linea.save(update_fields=['imagen', 'imagen_alt'])


def revertir_imagenes(apps, schema_editor):
    LineaServicio = apps.get_model('web_catalogo', 'LineaServicio')
    LineaServicio.objects.filter(slug__in=IMAGENES.keys()).update(imagen='', imagen_alt='')


class Migration(migrations.Migration):

    dependencies = [
        ('web_catalogo', '0007_backfill_miniaturas_galeria'),
    ]

    operations = [
        migrations.RunPython(poblar_imagenes, revertir_imagenes),
    ]
