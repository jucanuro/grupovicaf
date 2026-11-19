"""Quién ve cada tarjeta de la pantalla de entrada y quién entra al correo."""
from trabajadores.models import TrabajadorProfile
from trabajadores.permissions import trabajador_tiene_permiso

PERMISO_CORREO = 'correo.ver'
MODULO_CORREO = 'correo'


def puede_usar_correo(user):
    """Tarjeta Correos y acceso a email.<dominio>: permiso correo.ver."""
    return trabajador_tiene_permiso(user, PERMISO_CORREO)


def puede_entrar_correo(user):
    """Entrar a email.<dominio>: además de correo.ver, tener al menos una cuenta
    activa asignada (AccesoCuenta). Sin cuentas no hay nada que abrir; la única
    excepción es quien administra el correo, que entra para crearlas y asignarlas."""
    if not puede_usar_correo(user):
        return False
    from .models import AccesoCuenta
    if AccesoCuenta.objects.filter(usuario=user, cuenta__activa=True).exists():
        return True
    from .administracion import puede_administrar_algo
    return puede_administrar_algo(user)


def motivo_sin_correo(user):
    """'sin_permiso' (falta correo.ver) o 'sin_cuentas' (tiene el permiso pero ninguna cuenta)."""
    return 'sin_cuentas' if puede_usar_correo(user) else 'sin_permiso'


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
