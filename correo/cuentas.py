"""Acceso a cuentas, carpetas y mensajes: TODA vista pasa por aquí.

Regla: el acceso se valida en el servidor en cada consulta. Un objeto de una
cuenta sin AccesoCuenta responde 404 (no se revela que existe); un rol
insuficiente (p. ej. solo lectura que intenta mover) responde 403.
"""
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404

from .models import AccesoCuenta, CuentaCorreo, Hilo, Mensaje
from .permisos import puede_usar_correo

LECTURA, GESTIONA, ADMINISTRA = AccesoCuenta.LECTURA, AccesoCuenta.GESTIONA, AccesoCuenta.ADMINISTRA


def cuentas_de(user):
    """Cuentas activas que `user` puede abrir, con su contador de no leídos."""
    if not puede_usar_correo(user):
        return CuentaCorreo.objects.none()
    return (
        CuentaCorreo.objects.filter(activa=True, accesos__usuario=user)
        .annotate(no_leidos=Count(
            'mensajes', filter=Q(mensajes__leido=False, mensajes__carpeta__tipo='entrada'), distinct=True,
        ))
        .order_by('nombre')
    )


def roles_de(user):
    """{cuenta_id: rol} de las cuentas activas del usuario."""
    if not puede_usar_correo(user):
        return {}
    return dict(
        AccesoCuenta.objects.filter(usuario=user, cuenta__activa=True).values_list('cuenta_id', 'rol')
    )


def permite(rol, rol_minimo):
    return rol is not None and AccesoCuenta.NIVEL[rol] >= AccesoCuenta.NIVEL[rol_minimo]


def cuenta_de(user, slug):
    """La cuenta `slug` si `user` tiene acceso; si no, None."""
    return cuentas_de(user).filter(slug=slug).first()


def exigir_cuenta(user, slug=None, rol=LECTURA, pk=None):
    filtro = {'slug': slug} if slug is not None else {'pk': pk}
    cuenta = cuentas_de(user).filter(**filtro).first()
    if cuenta is None:
        raise Http404('Cuenta no disponible.')
    if not permite(roles_de(user).get(cuenta.pk), rol):
        raise PermissionDenied('Tu rol en esta cuenta no permite esta acción.')
    return cuenta


def mensajes_visibles(user):
    return Mensaje.objects.filter(cuenta__in=cuentas_de(user).values('pk'))


def hilos_visibles(user):
    return Hilo.objects.filter(cuenta__in=cuentas_de(user).values('pk'))


def exigir_mensaje(user, pk, rol=LECTURA):
    mensaje = mensajes_visibles(user).select_related('cuenta', 'carpeta', 'hilo').filter(pk=pk).first()
    if mensaje is None:
        raise Http404('Mensaje no disponible.')
    if not permite(roles_de(user).get(mensaje.cuenta_id), rol):
        raise PermissionDenied('Tu rol en esta cuenta no permite esta acción.')
    return mensaje


def exigir_hilo(user, pk, rol=LECTURA):
    hilo = hilos_visibles(user).select_related('cuenta').filter(pk=pk).first()
    if hilo is None:
        raise Http404('Conversación no disponible.')
    if not permite(roles_de(user).get(hilo.cuenta_id), rol):
        raise PermissionDenied('Tu rol en esta cuenta no permite esta acción.')
    return hilo
