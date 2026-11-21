"""Plazo de entrega al cliente según la oferta VCF-LAB-FOR-001.

Ensayos en probetas: los resultados se entregan dentro de las 24 horas
posteriores al ensayo; lo ensayado el sábado (o domingo) se entrega el lunes.
"""
from datetime import timedelta

from django.db.models import Max
from django.utils import timezone

SABADO, DOMINGO = 5, 6


def plazo_probeta(fecha_ensayo):
    """Fecha límite para entregar el resultado de una probeta ensayada ese día."""
    if fecha_ensayo is None:
        return None
    dias = {SABADO: 2, DOMINGO: 1}.get(fecha_ensayo.weekday(), 1)
    return fecha_ensayo + timedelta(days=dias)


def plazo_solicitud(solicitud):
    """Plazo de la solicitud: el de la probeta ensayada más tarde (None si ninguna tiene fecha)."""
    ultima = solicitud.detalles.aggregate(m=Max('resultado__fecha_ensayo'))['m']
    return plazo_probeta(ultima)


def estado_plazo(plazo, entregado=False, hoy=None):
    """'ok', 'hoy' o 'vencido' (None sin plazo o ya entregado)."""
    if plazo is None or entregado:
        return None
    hoy = hoy or timezone.localdate()
    if plazo < hoy:
        return 'vencido'
    if plazo == hoy:
        return 'hoy'
    return 'ok'
