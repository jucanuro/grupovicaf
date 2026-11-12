"""Quién ve cada tarjeta de la pantalla de entrada y quién entra al correo."""
from trabajadores.models import TrabajadorProfile
from trabajadores.permissions import trabajador_tiene_permiso

PERMISO_CORREO = 'correo.ver'
MODULO_CORREO = 'correo'


def puede_usar_correo(user):
    """Tarjeta Correos y acceso a email.<dominio>: permiso correo.ver."""
    return trabajador_tiene_permiso(user, PERMISO_CORREO)


def puede_usar_sistema(user):
    """Tarjeta Sistema (LIMS): superusuario o al menos un permiso que no sea del correo."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        rol = user.trabajadorprofile.rol
    except TrabajadorProfile.DoesNotExist:
        return False
    return rol.permisos.exclude(modulo_sistema__codigo=MODULO_CORREO).exists()
