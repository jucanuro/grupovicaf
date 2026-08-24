"""Lógica de negocio para convertir una SolicitudCotizacionWeb en registros del LIMS.

Separado de la vista a propósito: la vista solo valida entrada HTTP: esta
función encapsula la transacción que toca clientes.Cliente y servicios.Cotizacion.
"""
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.text import Truncator

from clientes.models import Cliente
from servicios.models import CotizacionDetalle, CotizacionGrupo, Cotizacion

NUMERO_OFERTA_PREFIJO = 'VCF-OTE'


def _obtener_o_crear_cliente(solicitud):
    """Busca por RUC; si no existe, crea inactivo y marcado como origen web.

    select_for_update() bloquea la fila existente para evitar que dos envíos
    concurrentes con el mismo RUC creen dos clientes; si ambos llegan a crear
    (RUC aún no existía en ninguno de los dos), el segundo choca contra el
    unique=True de Cliente.ruc y se recupera con un segundo intento de lectura.
    """
    cliente = Cliente.objects.select_for_update().filter(ruc=solicitud.ruc).first()
    if cliente is not None:
        return cliente

    try:
        return Cliente.objects.create(
            ruc=solicitud.ruc,
            razon_social=solicitud.razon_social,
            persona_contacto=solicitud.persona_contacto,
            celular_contacto=solicitud.telefono_contacto,
            correo_contacto=solicitud.correo_contacto,
            activo=False,
            creado_por=None,
            origen='web',
        )
    except IntegrityError:
        return Cliente.objects.get(ruc=solicitud.ruc)


def _siguiente_numero_oferta():
    """Replica el esquema de numeración de servicios/views.py (VCF-OTE-<año>-NNN)."""
    year_part = str(timezone.now().year)
    prefix_year = f'{NUMERO_OFERTA_PREFIJO}-{year_part}-'

    ultimo = (
        Cotizacion.objects.select_for_update()
        .filter(numero_oferta__startswith=prefix_year)
        .aggregate(Max('numero_oferta'))['numero_oferta__max']
    )
    siguiente = 1
    if ultimo:
        try:
            siguiente = int(ultimo.split('-')[-1]) + 1
        except (IndexError, ValueError):
            siguiente = 1
    return f'{prefix_year}{str(siguiente).zfill(3)}'


def _armar_asunto(items):
    titulos = [item.servicio_publicado.titulo_publico for item in items]
    asunto = 'Solicitud web: ' + ', '.join(titulos)
    return Truncator(asunto).chars(255)


def _armar_observaciones(solicitud):
    partes = [f'Solicitud generada desde {solicitud.origen or "/contacto/"}.']
    if solicitud.zona_id:
        partes.append(f'Zona de interés: {solicitud.zona.nombre}.')
    partes.append('Necesidad descrita por el visitante:')
    partes.append(solicitud.necesidad)
    return '\n'.join(partes)


@transaction.atomic
def procesar_solicitud_cotizacion(solicitud):
    """Crea (o reutiliza) el Cliente y genera la Cotizacion pendiente + detalles.

    Requiere que `solicitud` ya tenga sus SolicitudCotizacionItem guardados,
    cada uno con servicio_publicado.servicio no nulo (la vista filtra el
    selector público para no ofrecer ServicioPublicado sin vínculo al LIMS).
    """
    items = list(
        solicitud.items.select_related('servicio_publicado', 'servicio_publicado__servicio')
    )

    cliente = _obtener_o_crear_cliente(solicitud)

    cotizacion = Cotizacion.objects.create(
        cliente=cliente,
        numero_oferta=_siguiente_numero_oferta(),
        fecha_generacion=timezone.now().date(),
        asunto_servicio=_armar_asunto(items),
        persona_contacto=solicitud.persona_contacto,
        correo_contacto=solicitud.correo_contacto,
        telefono_contacto=solicitud.telefono_contacto,
        estado='Pendiente',
        observaciones_condiciones=_armar_observaciones(solicitud),
    )

    grupo = CotizacionGrupo.objects.create(
        cotizacion=cotizacion,
        nombre_grupo='SOLICITUD WEB',
        orden=0,
    )

    for item in items:
        servicio = item.servicio_publicado.servicio
        if servicio is None:
            continue
        CotizacionDetalle.objects.create(
            grupo=grupo,
            servicio=servicio,
            descripcion_especifica=item.servicio_publicado.titulo_publico,
            unidad_medida=servicio.unidad_base,
            cantidad=item.cantidad_estimada,
            precio_unitario=servicio.precio_base,
        )

    solicitud.cliente = cliente
    solicitud.cotizacion = cotizacion
    solicitud.save(update_fields=['cliente', 'cotizacion'])

    return cotizacion
