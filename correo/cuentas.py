"""Cuentas de correo a las que accede cada usuario.

PASO 1 (provisional): todavía no existen los modelos CuentaCorreo /
AccesoCuenta (llegan en el Paso 3, tras aprobar el modelo de datos). Mientras
tanto, quien tiene correo.ver ve estas cuentas de EJEMPLO con contadores
fijos. Las pantallas solo usan `cuentas_de()` y `cuenta_de()`, así que en el
Paso 3 cambia esta función y no las vistas.
"""
from dataclasses import dataclass

from .permisos import puede_usar_correo


@dataclass(frozen=True)
class CuentaVista:
    slug: str
    direccion: str
    nombre: str
    no_leidos: int


CUENTAS_EJEMPLO = (
    CuentaVista('informes', 'informes@grupovicaf.com', 'Informes y cotizaciones', 12),
    CuentaVista('laboratorio', 'laboratorio@grupovicaf.com', 'Laboratorio', 3),
    CuentaVista('quejas', 'quejas.reportes@grupovicaf.com', 'Quejas y reportes', 0),
)


def cuentas_de(user):
    """Cuentas que `user` puede abrir. Lista vacía si no tiene correo.ver."""
    if not puede_usar_correo(user):
        return []
    return list(CUENTAS_EJEMPLO)


def cuenta_de(user, slug):
    """La cuenta `slug` si `user` tiene acceso; si no, None (la vista responde 404)."""
    return next((c for c in cuentas_de(user) if c.slug == slug), None)
