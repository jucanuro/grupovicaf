"""Administración de cuentas de correo y de quién las abre (Paso 3).

Dos niveles, validados siempre en el servidor:
- Administrador del correo: superusuario o permiso `correo.administrar`. Crea
  cuentas, las activa o desactiva y gestiona los accesos de cualquiera.
- Quien tiene rol «administra» en una cuenta: cambia su nombre y sus accesos,
  pero no crea cuentas ni toca otras.

Administrar NO da acceso a leer el correo: para abrir una cuenta hace falta un
AccesoCuenta propio (y queda en la bitácora quién se lo dio).
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import Http404
from django.utils.text import slugify

from trabajadores.permissions import trabajador_tiene_permiso

from .mensajeria import asegurar_carpetas
from .models import AccesoCuenta, CuentaCorreo, EventoCuenta
from .permisos import PERMISO_CORREO, puede_usar_correo

PERMISO_ADMINISTRAR = 'correo.administrar'


def es_admin_correo(user):
    return user.is_authenticated and (user.is_superuser or trabajador_tiene_permiso(user, PERMISO_ADMINISTRAR))


def cuentas_administrables(user):
    """Todas (admin del correo) o las que el usuario administra; incluye inactivas."""
    if es_admin_correo(user):
        return CuentaCorreo.objects.all()
    if not puede_usar_correo(user):
        return CuentaCorreo.objects.none()
    return CuentaCorreo.objects.filter(accesos__usuario=user, accesos__rol=AccesoCuenta.ADMINISTRA)


def puede_administrar_algo(user):
    return es_admin_correo(user) or cuentas_administrables(user).exists()


def exigir_cuenta_administrable(user, slug):
    cuenta = cuentas_administrables(user).filter(slug=slug).first()
    if cuenta is None:
        raise Http404('Cuenta no disponible.')
    return cuenta


def registrar(cuenta, usuario, tipo, **detalle):
    detalle.setdefault('cuenta', cuenta.direccion)
    return EventoCuenta.objects.create(cuenta=cuenta, usuario=usuario, tipo=tipo, detalle=detalle)


def validar_direccion(direccion):
    direccion = (direccion or '').strip().lower()
    try:
        validate_email(direccion)
    except ValidationError:
        raise ValidationError('Escribe una dirección de correo válida.')
    dominio = direccion.rsplit('@', 1)[1]
    if dominio not in settings.CORREO_DOMINIOS:
        raise ValidationError(f'La dirección debe ser @{" o @".join(settings.CORREO_DOMINIOS)}.')
    if CuentaCorreo.objects.filter(direccion=direccion).exists():
        raise ValidationError('Ya existe una cuenta con esa dirección.')
    return direccion


def _slug_libre(direccion):
    base = slugify(direccion.split('@')[0].replace('.', '-')) or 'cuenta'
    slug, n = base[:40], 2
    while CuentaCorreo.objects.filter(slug=slug).exists():
        slug, n = f'{base[:36]}-{n}', n + 1
    return slug


def crear_cuenta(actor, *, direccion, nombre, darme_acceso=True):
    if not es_admin_correo(actor):
        raise PermissionDenied('Solo un administrador del correo crea cuentas.')
    direccion = validar_direccion(direccion)
    nombre = (nombre or '').strip()[:120] or direccion.split('@')[0].title()
    with transaction.atomic():
        cuenta = CuentaCorreo.objects.create(direccion=direccion, nombre=nombre, slug=_slug_libre(direccion))
        asegurar_carpetas(cuenta)
        registrar(cuenta, actor, EventoCuenta.CREO, nombre=nombre)
        if darme_acceso:
            AccesoCuenta.objects.create(usuario=actor, cuenta=cuenta, rol=AccesoCuenta.ADMINISTRA)
            registrar(cuenta, actor, EventoCuenta.DIO_ACCESO, a=_nombre(actor), rol=AccesoCuenta.ADMINISTRA)
    return cuenta


def renombrar_cuenta(actor, cuenta, nombre):
    nombre = (nombre or '').strip()[:120]
    if nombre and nombre != cuenta.nombre:
        anterior, cuenta.nombre = cuenta.nombre, nombre
        cuenta.save(update_fields=['nombre'])
        registrar(cuenta, actor, EventoCuenta.EDITO, nombre=[anterior, nombre])
    return cuenta


def cambiar_estado(actor, cuenta, activa):
    if not es_admin_correo(actor):
        raise PermissionDenied('Solo un administrador del correo activa o desactiva cuentas.')
    if cuenta.activa != activa:
        cuenta.activa = activa
        cuenta.save(update_fields=['activa'])
        registrar(cuenta, actor, EventoCuenta.ACTIVO if activa else EventoCuenta.DESACTIVO)


def usuarios_asignables():
    """Trabajadores activos (un usuario del portal de clientes nunca recibe acceso)."""
    return (get_user_model().objects.filter(is_active=True, trabajadorprofile__isnull=False)
            .select_related('trabajadorprofile').order_by('trabajadorprofile__nombre_completo', 'username'))


def _nombre(user):
    perfil = getattr(user, 'trabajadorprofile', None)
    return (perfil and perfil.nombre_completo) or user.get_full_name() or user.username


def _quedan_administradores(cuenta, sin):
    return cuenta.accesos.filter(rol=AccesoCuenta.ADMINISTRA).exclude(pk=sin.pk).exists()


def dar_acceso(actor, cuenta, usuario, rol):
    if rol not in AccesoCuenta.NIVEL:
        raise ValidationError('Rol no válido.')
    if not usuarios_asignables().filter(pk=usuario.pk).exists():
        raise ValidationError('Solo se da acceso a trabajadores activos.')
    acceso, creado = AccesoCuenta.objects.get_or_create(usuario=usuario, cuenta=cuenta, defaults={'rol': rol})
    if creado:
        registrar(cuenta, actor, EventoCuenta.DIO_ACCESO, a=_nombre(usuario), rol=rol)
    elif acceso.rol != rol:
        cambiar_rol(actor, acceso, rol)
    return acceso


def cambiar_rol(actor, acceso, rol):
    if rol not in AccesoCuenta.NIVEL:
        raise ValidationError('Rol no válido.')
    if acceso.rol == rol:
        return acceso
    if (acceso.rol == AccesoCuenta.ADMINISTRA and not es_admin_correo(actor)
            and not _quedan_administradores(acceso.cuenta, acceso)):
        raise ValidationError('La cuenta debe quedar con al menos una persona que la administre.')
    anterior, acceso.rol = acceso.rol, rol
    acceso.save(update_fields=['rol'])
    registrar(acceso.cuenta, actor, EventoCuenta.CAMBIO_ROL, a=_nombre(acceso.usuario), de=anterior, rol=rol)
    return acceso


def quitar_acceso(actor, acceso):
    if (acceso.rol == AccesoCuenta.ADMINISTRA and not es_admin_correo(actor)
            and not _quedan_administradores(acceso.cuenta, acceso)):
        raise ValidationError('La cuenta debe quedar con al menos una persona que la administre.')
    registrar(acceso.cuenta, actor, EventoCuenta.QUITO_ACCESO, a=_nombre(acceso.usuario), rol=acceso.rol)
    acceso.delete()


def sin_permiso_correo(usuarios):
    """pk de los que tienen acceso pero no `correo.ver` (no verán la cuenta hasta tenerlo)."""
    return {u.pk for u in usuarios if not trabajador_tiene_permiso(u, PERMISO_CORREO)}
