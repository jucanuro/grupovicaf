from .permissions import trabajador_tiene_permiso


def permisos_usuario(request):
    user = request.user

    if not user.is_authenticated:
        return {}

    permisos = {
        'puede_ver_dashboard': trabajador_tiene_permiso(user, 'dashboard.ver'),
        'puede_ver_administracion': trabajador_tiene_permiso(user, 'administracion.ver'),
        'puede_ver_clientes': trabajador_tiene_permiso(user, 'clientes.ver'),
        'puede_ver_trabajadores': trabajador_tiene_permiso(user, 'trabajadores.ver'),
        'puede_ver_roles': trabajador_tiene_permiso(user, 'roles.ver'),
        'puede_ver_permisos': trabajador_tiene_permiso(user, 'roles.permisos'),
        'puede_ver_servicios': trabajador_tiene_permiso(user, 'servicios.ver'),
        'puede_ver_cotizaciones': trabajador_tiene_permiso(user, 'cotizaciones.ver'),
        'puede_ver_proyectos': trabajador_tiene_permiso(user, 'proyectos.ver'),
        'puede_ver_muestras': trabajador_tiene_permiso(user, 'muestras.ver'),
        'puede_ver_ensayos': trabajador_tiene_permiso(user, 'ensayos.ver'),
        'puede_ver_informes': trabajador_tiene_permiso(user, 'informes.ver'),
        'puede_ver_calendario': trabajador_tiene_permiso(user, 'calendario.ver'),
        'puede_ver_gantt': trabajador_tiene_permiso(user, 'gantt.ver'),
    }

    permisos['total_modulos_visibles'] = sum(1 for value in permisos.values() if value is True)

    return permisos