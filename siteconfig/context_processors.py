from .models import NegocioConfig


def negocio(request):
    """Expone la configuración de negocio (NAP) a toda plantilla."""
    return {'negocio': NegocioConfig.objects.first()}
