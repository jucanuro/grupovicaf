from core.models import siguiente_correlativo

PREFIJO_OFERTA = 'VCF-OTE'


def siguiente_numero_oferta(anio):
    """VCF-OTE-<año>-NNN, compartido por el formulario del LIMS y la bandeja web."""
    from .models import Cotizacion

    prefijo = f'{PREFIJO_OFERTA}-{anio}-'
    numero = siguiente_correlativo(
        prefijo,
        Cotizacion.objects.filter(numero_oferta__startswith=prefijo).values_list('numero_oferta', flat=True),
    )
    return f'{prefijo}{numero:03d}'
