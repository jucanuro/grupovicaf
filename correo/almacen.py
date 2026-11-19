"""Dónde se guardan los .eml y los adjuntos del correo.

Nunca en MEDIA_ROOT (nginx lo sirve en público).
- CORREO_ALMACEN=local (dev y pruebas): carpeta privada CORREO_ALMACEN_DIR.
- CORREO_ALMACEN=r2 (producción): bucket PRIVADO de Cloudflare R2 vía
  django-storages (API S3). Sin ACL pública; los objetos solo se leen con una
  URL prefirmada de CORREO_URL_FIRMADA_SEGUNDOS (300 s), que se emite después
  de validar el acceso del usuario a la cuenta (ver views_correo.adjunto).

boto3 se importa solo en modo r2: en local no ocupa memoria.
"""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.utils.functional import LazyObject


def es_r2():
    return settings.CORREO_ALMACEN == 'r2'


def crear_almacen_r2():
    faltan = [n for n in ('CORREO_R2_BUCKET', 'CORREO_R2_ENDPOINT', 'CORREO_R2_ACCESS_KEY', 'CORREO_R2_SECRET_KEY')
              if not getattr(settings, n)]
    if faltan:
        raise ImproperlyConfigured(f'CORREO_ALMACEN=r2 pero falta en el .env: {", ".join(faltan)}.')
    from storages.backends.s3 import S3Storage  # import perezoso (boto3)
    return S3Storage(
        bucket_name=settings.CORREO_R2_BUCKET,
        endpoint_url=settings.CORREO_R2_ENDPOINT,
        access_key=settings.CORREO_R2_ACCESS_KEY,
        secret_key=settings.CORREO_R2_SECRET_KEY,
        region_name='auto',
        signature_version='s3v4',
        addressing_style='path',
        default_acl=None,               # R2 no usa ACL: el bucket es privado
        querystring_auth=True,          # toda URL lleva firma…
        querystring_expire=settings.CORREO_URL_FIRMADA_SEGUNDOS,  # …y vence
        file_overwrite=False,           # nunca pisar un adjunto existente
        custom_domain=None,
    )


class _AlmacenCorreo(LazyObject):
    def _setup(self):
        if es_r2():
            self._wrapped = crear_almacen_r2()
        else:
            self._wrapped = FileSystemStorage(location=settings.CORREO_ALMACEN_DIR, base_url=None)


almacen_correo = _AlmacenCorreo()


def obtener_almacen():
    return almacen_correo


def url_prefirmada(nombre, *, descarga, tipo, en_linea=False):
    """URL de R2 válida CORREO_URL_FIRMADA_SEGUNDOS que fuerza nombre y tipo del archivo."""
    from urllib.parse import quote
    disposicion = 'inline' if en_linea else 'attachment'
    return almacen_correo.url(nombre, parameters={
        'ResponseContentDisposition': f"{disposicion}; filename*=UTF-8''{quote(descarga)}",
        'ResponseContentType': tipo,
    }, expire=settings.CORREO_URL_FIRMADA_SEGUNDOS)
