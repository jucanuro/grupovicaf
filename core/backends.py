"""Inicio de sesión con nombre de usuario o con correo."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsuarioOCorreoBackend(ModelBackend):
    """Acepta el nombre de usuario (como siempre) o el correo de la ficha.

    El correo solo sirve si identifica a UN usuario activo (sin mayúsculas ni
    espacios de por medio); si dos usuarios lo comparten, no entra por correo
    y debe usar su nombre de usuario. La contraseña se valida igual que siempre.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        username = str(username).strip()
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is not None or '@' not in username:
            return user
        candidatos = list(get_user_model().objects.filter(email__iexact=username, is_active=True)[:2])
        if len(candidatos) != 1:
            return None
        return super().authenticate(request, username=candidatos[0].get_username(), password=password, **kwargs)
