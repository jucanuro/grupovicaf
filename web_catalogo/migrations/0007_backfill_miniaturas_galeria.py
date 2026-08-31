"""Genera imagen_miniatura para las ImagenLinea sembradas por
0005_infohtml_y_galeria_lineas, que corrieron antes de que el modelo supiera
generar miniaturas en save() (ver ImagenLinea.save en models.py). Sin esto,
esas filas seguirían sirviendo el archivo de 1600px como "miniatura" en la
grilla — justo el problema de peso que introdujo la miniatura en primer lugar.
"""
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import migrations
from PIL import Image

ANCHO_MINIATURA = 480
CALIDAD_MINIATURA = 70


def generar_miniaturas_faltantes(apps, schema_editor):
    ImagenLinea = apps.get_model('web_catalogo', 'ImagenLinea')
    for foto in ImagenLinea.objects.filter(imagen_miniatura=''):
        if not foto.imagen:
            continue
        foto.imagen.open('rb')
        with Image.open(foto.imagen) as fuente:
            miniatura = fuente.convert('RGB')
            if miniatura.width > ANCHO_MINIATURA:
                alto = round(miniatura.height * ANCHO_MINIATURA / miniatura.width)
                miniatura = miniatura.resize((ANCHO_MINIATURA, alto), Image.LANCZOS)
            buffer = BytesIO()
            miniatura.save(buffer, format='WEBP', quality=CALIDAD_MINIATURA)
        nombre = f'{Path(foto.imagen.name).stem}_mini.webp'
        foto.imagen_miniatura.save(nombre, ContentFile(buffer.getvalue()), save=False)
        foto.save(update_fields=['imagen_miniatura', 'ancho_miniatura', 'alto_miniatura'])


def revertir(apps, schema_editor):
    ImagenLinea = apps.get_model('web_catalogo', 'ImagenLinea')
    ImagenLinea.objects.update(imagen_miniatura='', ancho_miniatura=0, alto_miniatura=0)


class Migration(migrations.Migration):

    dependencies = [
        ('web_catalogo', '0006_imagenlinea_miniatura'),
    ]

    operations = [
        migrations.RunPython(generar_miniaturas_faltantes, revertir),
    ]
