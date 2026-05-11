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