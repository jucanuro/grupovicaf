"""Procesado de las fotos del ensayo de compresión (HU-LIMS-14).

El navegador ya envía el recorte con la proporción del recuadro (Cropper.js),
pero el servidor no confía en eso: corrige la orientación del celular, recorta
al centro si la proporción no cuadra, reduce el lado mayor y guarda en JPEG.
Con fotos de ~1600 px tarda bastante menos de 1 s, por eso no va a Celery.
"""
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

# Margen admitido entre la proporción recibida y la del recuadro.
TOLERANCIA_PROPORCION = 0.02
# Tope de lo que se acepta subir (el navegador manda ~0,3-1 MB).
MAX_BYTES = 15 * 1024 * 1024
# Evita imágenes descomunales (bombas de descompresión).
MAX_PIXELES = 50_000_000


class FotoInvalida(ValueError):
    pass


def _recortar_al_centro(img, proporcion):
    ancho, alto = img.size
    if ancho / alto > proporcion:  # sobra ancho
        nuevo_ancho = round(alto * proporcion)
        izq = (ancho - nuevo_ancho) // 2
        return img.crop((izq, 0, izq + nuevo_ancho, alto))
    nuevo_alto = round(ancho / proporcion)
    arriba = (alto - nuevo_alto) // 2
    return img.crop((0, arriba, ancho, arriba + nuevo_alto))


def procesar_foto(archivo, proporcion, lado_maximo):
    """Devuelve un ContentFile JPEG listo para guardar, o lanza FotoInvalida."""
    if archivo.size > MAX_BYTES:
        raise FotoInvalida("La foto pesa más de 15 MB.")
    try:
        img = Image.open(archivo)
        if img.width * img.height > MAX_PIXELES:
            raise FotoInvalida("La foto tiene demasiados píxeles.")
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise FotoInvalida("El archivo no es una imagen válida.")

    img = ImageOps.exif_transpose(img)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # proporcion=None: la foto conserva la suya (galería del ensayo general).
    if proporcion and abs(img.width / img.height - proporcion) / proporcion > TOLERANCIA_PROPORCION:
        img = _recortar_al_centro(img, proporcion)

    if max(img.size) > lado_maximo:
        img.thumbnail((lado_maximo, lado_maximo), Image.LANCZOS)

    salida = BytesIO()
    img.save(salida, format='JPEG', quality=85, optimize=True)
    return ContentFile(salida.getvalue(), name='foto.jpg')
