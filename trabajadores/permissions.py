from functools import wraps
from django.http import HttpResponseForbidden
from .models import TrabajadorProfile


def trabajador_tiene_permiso(user, codigo_permiso):
    if user.is_superuser:
        return True

    if not user.is_authenticated:
        return False

    try:
        perfil = user.trabajadorprofile
        return perfil.rol.permisos.filter(codigo=codigo_permiso).exists()
    except TrabajadorProfile.DoesNotExist:
        return False


def permiso_requerido(codigo_permiso):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not trabajador_tiene_permiso(request.user, codigo_permiso):
                return HttpResponseForbidden("No tienes permiso para acceder a esta sección.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# Sin este permiso el trabajador (p. ej. el técnico) solo ve las solicitudes
# de ensayo donde tiene algún ensayo asignado y nunca el nombre del cliente:
# en su lugar ve el código confidencial (CLI-AA-NNNN), como en el FOR-068.
PERMISO_VER_TODOS_ENSAYOS = 'ensayos.ver_todos'


def ve_todos_los_ensayos(user):
    return trabajador_tiene_permiso(user, PERMISO_VER_TODOS_ENSAYOS)


def nombre_cliente_visible(user, cliente, ve_todos=None):
    """Razón social o código confidencial según el permiso del usuario."""
    if cliente is None:
        return ''
    if ve_todos is None:
        ve_todos = ve_todos_los_ensayos(user)
    return cliente.razon_social if ve_todos else (cliente.codigo_confidencial or '')
