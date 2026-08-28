"""Invalidación de la caché de 15 min de las vistas de listado (regla 6).

Solo se cachean listados (servicios_list_view, clientes_list_view,
equipo_list_view); el detalle de servicio no se cachea, así que no necesita
invalidación. Cada clave se limpia cuando cambia su companion o el modelo
del LIMS que consume.
"""
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save

from clientes.models import Cliente
from servicios.models import Servicio
from trabajadores.models import TrabajadorProfile

from .cache import KEY_CLIENTES_LIST, KEY_EQUIPO_LIST, KEY_SERVICIOS_LIST
from .models import ClienteDestacado, MiembroEquipoPublicado, ServicioPublicado


def _invalidar(clave):
    def _handler(sender, **kwargs):
        cache.delete(clave)
    return _handler


_invalidar_servicios = _invalidar(KEY_SERVICIOS_LIST)
_invalidar_clientes = _invalidar(KEY_CLIENTES_LIST)
_invalidar_equipo = _invalidar(KEY_EQUIPO_LIST)

for modelo in (ServicioPublicado, Servicio):
    post_save.connect(_invalidar_servicios, sender=modelo, weak=False)
    post_delete.connect(_invalidar_servicios, sender=modelo, weak=False)

for modelo in (ClienteDestacado, Cliente):
    post_save.connect(_invalidar_clientes, sender=modelo, weak=False)
    post_delete.connect(_invalidar_clientes, sender=modelo, weak=False)

for modelo in (MiembroEquipoPublicado, TrabajadorProfile):
    post_save.connect(_invalidar_equipo, sender=modelo, weak=False)
    post_delete.connect(_invalidar_equipo, sender=modelo, weak=False)
