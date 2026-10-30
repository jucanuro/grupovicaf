"""Ayudas para los tests de permisos por rol (no se importa en producción)."""
from django.contrib.auth.models import User

from .models import AccionPermiso, ModuloSistema, PermisoModulo, RolTrabajador, TrabajadorProfile


def rol_con_permisos(nombre, *codigos):
    """RolTrabajador con los permisos 'modulo.accion' indicados (los crea si faltan)."""
    rol = RolTrabajador.objects.create(nombre=nombre)
    for codigo in codigos:
        modulo_codigo, accion_codigo = codigo.split('.')
        modulo, _ = ModuloSistema.objects.get_or_create(
            codigo=modulo_codigo, defaults={'nombre': modulo_codigo.title()},
        )
        accion, _ = AccionPermiso.objects.get_or_create(
            codigo=accion_codigo, defaults={'nombre': accion_codigo.title()},
        )
        permiso, _ = PermisoModulo.objects.get_or_create(modulo_sistema=modulo, accion=accion)
        rol.permisos.add(permiso)
    return rol


def crear_trabajador(username, rol, nombre_completo=None):
    user = User.objects.create_user(username, password='x')
    perfil = TrabajadorProfile.objects.create(
        user=user, rol=rol, nombre_completo=nombre_completo or username,
    )
    return user, perfil
