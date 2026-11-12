"""Dónde se guardan los .eml y los adjuntos del correo.

Nunca en MEDIA_ROOT (nginx lo sirve en público). En desarrollo y pruebas, una
carpeta privada del disco (CORREO_ALMACEN_DIR). En el Paso 3 se conecta el
bucket privado de Cloudflare R2 vía django-storages sin cambiar los modelos.
Las descargas pasan siempre por un enlace firmado de corta duración
(correo.enlaces.url_firmada_adjunto).
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.functional import LazyObject


class _AlmacenCorreo(LazyObject):
    def _setup(self):
        self._wrapped = FileSystemStorage(location=settings.CORREO_ALMACEN_DIR, base_url=None)


almacen_correo = _AlmacenCorreo()


def obtener_almacen():
    return almacen_correo
