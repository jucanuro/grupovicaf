"""Obliga a cambiar la contraseña temporal antes de usar el sistema."""
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse


class ClaveTemporalMiddleware:
    """Si el perfil tiene `debe_cambiar_clave`, solo deja ver «Cambiar mi contraseña» y salir.

    En hosts cuyo URLconf no tiene esa ruta (web pública, correo) no hace nada:
    al correo solo se entra con enlace firmado desde el LIMS, que ya pasó por aquí.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, 'user', None)
        if usuario is not None and usuario.is_authenticated and not request.path.startswith(('/static/', '/media/')):
            try:
                destino = reverse('cambiar_clave')
                salida = reverse('logout')
            except NoReverseMatch:
                destino = salida = None
            if destino and request.path not in (destino, salida):
                from trabajadores.models import TrabajadorProfile
                if TrabajadorProfile.objects.filter(user=usuario, debe_cambiar_clave=True).exists():
                    return redirect(destino)
        return self.get_response(request)
