"""Conjuntos de datos de Análisis (VCF-LIMS, HU-LIMS-06 a 10).

Cada conjunto declara:
- el permiso de su módulo (DP-LIMS-12 B), además de `reportes.ver`;
- la fecha sobre la que filtra el rango (RN-R01);
- su LISTA BLANCA de campos: solo esas claves llegan al navegador
  (CA-10.2, reglas 2 y 3 del CLAUDE.md). Un campo puede pedir un permiso
  extra (p. ej. los montos de Clientes exigen `cotizaciones.ver`);
- sus vistas rápidas (CA-08.1).

Para sumar un módulo basta con escribir otra subclase de `Conjunto` y
añadirla a `CONJUNTOS`: la pantalla y la exportación no cambian.

Nunca se exponen: RUC, código confidencial, firmas, logos, archivos,
código del voucher, slug de validación ni datos de contacto.
"""
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from trabajadores.permissions import trabajador_tiene_permiso

PERMISO_REPORTES = 'reportes.ver'
LIMITE_FILAS = 20_000

TEXTO = 'texto'
NUMERO = 'numero'


@dataclass(frozen=True)
class Campo:
    clave: str
    etiqueta: str
    tipo: str = TEXTO
    permiso: str | None = None


class FilasExcedidas(Exception):
    def __init__(self, total):
        super().__init__(total)
        self.total = total


def _num(valor):
    if valor is None:
        return 0
    if isinstance(valor, Decimal):
        return float(round(valor, 2))
    return valor


def _si_no(valor):
    return 'Sí' if valor else 'No'


def _mes(fecha):
    return f'{fecha:%Y-%m}' if fecha else ''


def _anio(fecha):
    return str(fecha.year) if fecha else ''


class Conjunto:
    clave = ''
    nombre = ''
    modulo = ''
    descripcion = ''
    permiso = ''
    campo_fecha = ''
    rango_defecto = 'mes'  # 'mes' (mes en curso) o 'todo'
    campos: tuple = ()
    vistas_rapidas: tuple = ()

    def puede_ver(self, user):
        return (trabajador_tiene_permiso(user, PERMISO_REPORTES)
                and trabajador_tiene_permiso(user, self.permiso))

    def campos_visibles(self, user):
        return [c for c in self.campos if c.permiso is None or trabajador_tiene_permiso(user, c.permiso)]

    def vistas_visibles(self, user):
        etiquetas = {c.etiqueta for c in self.campos_visibles(user)}
        visibles = []
        for vista in self.vistas_rapidas:
            usados = set(vista.get('rows', [])) | set(vista.get('cols', [])) | set(vista.get('vals', []))
            usados |= set(vista.get('inclusions', {})) | set(vista.get('exclusions', {}))
            if usados <= etiquetas:
                visibles.append(vista)
        return visibles

    def queryset(self):
        raise NotImplementedError

    def filtrar_fechas(self, qs, desde, hasta):
        if desde:
            qs = qs.filter(**{f'{self.campo_fecha}__gte': desde})
        if hasta:
            qs = qs.filter(**{f'{self.campo_fecha}__lte': hasta})
        return qs

    def registros(self, qs):
        """Itera dicts con las claves de `campos`. Puede traer claves de más:
        `datos()` solo copia las de la lista blanca."""
        raise NotImplementedError

    def datos(self, user, desde=None, hasta=None):
        qs = self.filtrar_fechas(self.queryset(), desde, hasta)
        total = qs.count()
        if total > LIMITE_FILAS:
            raise FilasExcedidas(total)
        campos = self.campos_visibles(user)
        filas = [[registro.get(c.clave) for c in campos] for registro in self.registros(qs)]
        return {
            'encabezado': [c.etiqueta for c in campos],
            'numericos': [c.etiqueta for c in campos if c.tipo == NUMERO],
            'filas': filas,
        }

    def resumen(self, user):
        return {
            'clave': self.clave,
            'nombre': self.nombre,
            'modulo': self.modulo,
            'descripcion': self.descripcion,
            'rango_defecto': self.rango_defecto,
            'vistas': self.vistas_visibles(user),
        }


# ----------------------------------------------------------------------
# Comercial
# ----------------------------------------------------------------------

def _etiquetas_forma_pago():
    from servicios.models import Cotizacion
    return dict(Cotizacion.FORMA_PAGO_CHOICES)


class Cotizaciones(Conjunto):
    clave = 'cotizaciones'
    nombre = 'Cotizaciones'
    modulo = 'Comercial'
    descripcion = 'Una fila por cotización emitida (sin plantillas). Montos en soles.'
    permiso = 'cotizaciones.ver'
    campo_fecha = 'fecha_generacion'
    campos = (
        Campo('numero', 'N.º oferta'),
        Campo('cliente', 'Cliente'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('fecha', 'Fecha'),
        Campo('estado', 'Estado'),
        Campo('forma_pago', 'Forma de pago'),
        Campo('responsable', 'Responsable'),
        Campo('categoria', 'Categoría'),
        Campo('con_voucher', 'Con voucher'),
        Campo('subtotal', 'Subtotal (sin IGV)', NUMERO),
        Campo('igv', 'IGV', NUMERO),
        Campo('total', 'Total (con IGV)', NUMERO),
        Campo('cobrado', 'Cobrado (voucher)', NUMERO),
        Campo('saldo', 'Saldo referencial', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Total por cliente', 'rows': ['Cliente'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['Total (con IGV)'], 'rendererName': 'Tabla',
         'rowOrder': 'value_z_to_a'},
        {'nombre': 'Cantidad por mes y estado', 'rows': ['Mes'], 'cols': ['Estado'],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Barras apiladas'},
        {'nombre': 'Monto por estado', 'rows': ['Estado'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['Total (con IGV)'], 'rendererName': 'Tabla'},
        {'nombre': 'Saldo referencial por cliente', 'rows': ['Cliente'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['Saldo referencial'], 'rendererName': 'Tabla',
         'inclusions': {'Estado': ['Aceptada']}, 'rowOrder': 'value_z_to_a'},
        {'nombre': 'Por forma de pago', 'rows': ['Forma de pago'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['Total (con IGV)'], 'rendererName': 'Dona'},
    )

    def queryset(self):
        from servicios.models import Cotizacion
        return Cotizacion.objects.filter(es_plantilla=False)

    def registros(self, qs):
        formas = _etiquetas_forma_pago()
        valores = qs.order_by('fecha_generacion', 'id').values(
            'numero_oferta', 'cliente__razon_social', 'fecha_generacion', 'estado', 'forma_pago',
            'trabajador_responsable__nombre_completo', 'servicio_general__nombre',
            'subtotal', 'impuesto_igv', 'monto_total', 'voucher__monto_pagado',
        )
        for v in valores:
            total = v['monto_total'] or Decimal('0')
            cobrado = v['voucher__monto_pagado'] or Decimal('0')
            # RN-R02: solo las aceptadas tienen saldo; es referencial (V-01 a V-04).
            saldo = max(total - cobrado, Decimal('0')) if v['estado'] == 'Aceptada' else Decimal('0')
            fecha = v['fecha_generacion']
            yield {
                'numero': v['numero_oferta'] or 'S/N',
                'cliente': v['cliente__razon_social'] or '',
                'anio': _anio(fecha),
                'mes': _mes(fecha),
                'fecha': fecha.isoformat() if fecha else '',
                'estado': v['estado'],
                'forma_pago': formas.get(v['forma_pago'], v['forma_pago']),
                'responsable': v['trabajador_responsable__nombre_completo'] or 'Sin asignar',
                'categoria': v['servicio_general__nombre'] or 'Sin categoría',
                'con_voucher': _si_no(v['voucher__monto_pagado'] is not None),
                'subtotal': _num(v['subtotal']),
                'igv': _num(v['impuesto_igv']),
                'total': _num(total),
                'cobrado': _num(cobrado),
                'saldo': _num(saldo),
            }


class ItemsCotizados(Conjunto):
    clave = 'items'
    nombre = 'Ítems cotizados'
    modulo = 'Comercial'
    descripcion = 'Una fila por ensayo de cada cotización. Montos sin IGV.'
    permiso = 'cotizaciones.ver'
    campo_fecha = 'grupo__cotizacion__fecha_generacion'
    campos = (
        Campo('numero', 'N.º oferta'),
        Campo('cliente', 'Cliente'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('estado', 'Estado de la cotización'),
        Campo('forma_pago', 'Forma de pago'),
        Campo('responsable', 'Responsable'),
        Campo('grupo', 'Grupo'),
        Campo('codigo', 'Código de ensayo'),
        Campo('ensayo', 'Ensayo'),
        Campo('acreditado', 'Acreditado'),
        Campo('unidad', 'Unidad'),
        Campo('cantidad', 'Cantidad', NUMERO),
        Campo('precio', 'Precio unitario (sin IGV)', NUMERO),
        Campo('total', 'Total ítem (sin IGV)', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Monto por ensayo', 'rows': ['Ensayo'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['Total ítem (sin IGV)'], 'rendererName': 'Tabla',
         'rowOrder': 'value_z_to_a'},
        {'nombre': 'Cantidad por ensayo y mes', 'rows': ['Ensayo'], 'cols': ['Mes'],
         'aggregatorName': 'Suma', 'vals': ['Cantidad'], 'rendererName': 'Tabla'},
        {'nombre': 'Aceptado por ensayo', 'rows': ['Ensayo'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['Total ítem (sin IGV)'], 'rendererName': 'Barras',
         'inclusions': {'Estado de la cotización': ['Aceptada']}, 'rowOrder': 'value_z_to_a'},
    )

    def queryset(self):
        from servicios.models import CotizacionDetalle
        return CotizacionDetalle.objects.filter(grupo__cotizacion__es_plantilla=False)

    def registros(self, qs):
        formas = _etiquetas_forma_pago()
        valores = qs.order_by('grupo__cotizacion__fecha_generacion', 'id').values(
            'grupo__cotizacion__numero_oferta', 'grupo__cotizacion__cliente__razon_social',
            'grupo__cotizacion__fecha_generacion', 'grupo__cotizacion__estado',
            'grupo__cotizacion__forma_pago', 'grupo__cotizacion__trabajador_responsable__nombre_completo',
            'grupo__nombre_grupo', 'servicio__codigo_facturacion', 'servicio__nombre',
            'servicio__esta_acreditado', 'unidad_medida', 'cantidad', 'precio_unitario', 'total_detalle',
        )
        for v in valores:
            fecha = v['grupo__cotizacion__fecha_generacion']
            forma = v['grupo__cotizacion__forma_pago']
            yield {
                'numero': v['grupo__cotizacion__numero_oferta'] or 'S/N',
                'cliente': v['grupo__cotizacion__cliente__razon_social'] or '',
                'anio': _anio(fecha),
                'mes': _mes(fecha),
                'estado': v['grupo__cotizacion__estado'],
                'forma_pago': formas.get(forma, forma),
                'responsable': v['grupo__cotizacion__trabajador_responsable__nombre_completo'] or 'Sin asignar',
                'grupo': v['grupo__nombre_grupo'] or '',
                'codigo': v['servicio__codigo_facturacion'] or '',
                'ensayo': v['servicio__nombre'] or '',
                'acreditado': _si_no(v['servicio__esta_acreditado']),
                'unidad': v['unidad_medida'] or '',
                'cantidad': _num(v['cantidad']),
                'precio': _num(v['precio_unitario']),
                'total': _num(v['total_detalle']),
            }


# ----------------------------------------------------------------------
# Clientes
# ----------------------------------------------------------------------

class Clientes(Conjunto):
    clave = 'clientes'
    nombre = 'Clientes'
    modulo = 'Clientes'
    descripcion = 'Una fila por cliente. El rango filtra por fecha de alta; los totales son históricos.'
    permiso = 'clientes.ver'
    campo_fecha = 'creado_en__date'
    rango_defecto = 'todo'
    campos = (
        Campo('razon_social', 'Razón social'),
        Campo('origen', 'Origen'),
        Campo('activo', 'Activo'),
        Campo('anio', 'Año de alta'),
        Campo('mes', 'Mes de alta'),
        Campo('n_cotizaciones', 'N.º cotizaciones', NUMERO),
        Campo('n_aceptadas', 'N.º aceptadas', NUMERO),
        Campo('monto', 'Monto cotizado (con IGV)', NUMERO, permiso='cotizaciones.ver'),
        Campo('monto_aceptado', 'Monto aceptado (con IGV)', NUMERO, permiso='cotizaciones.ver'),
        Campo('n_proyectos', 'N.º proyectos', NUMERO),
        Campo('n_informes', 'N.º informes', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Cotizado por cliente', 'rows': ['Razón social'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['Monto cotizado (con IGV)'], 'rendererName': 'Tabla',
         'rowOrder': 'value_z_to_a'},
        {'nombre': 'Clientes nuevos por mes', 'rows': ['Mes de alta'], 'cols': ['Origen'],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Barras apiladas'},
        {'nombre': 'Informes por cliente', 'rows': ['Razón social'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['N.º informes'], 'rendererName': 'Tabla',
         'rowOrder': 'value_z_to_a'},
    )

    def queryset(self):
        from clientes.models import Cliente
        return Cliente.objects.all()

    def registros(self, qs):
        from clientes.models import Cliente
        from proyectos.models import InformeFinal, Proyecto
        from servicios.models import Cotizacion

        aceptada = Q(estado='Aceptada')
        cotizaciones = {
            fila['cliente_id']: fila
            for fila in Cotizacion.objects.filter(es_plantilla=False).values('cliente_id').annotate(
                n=Count('id'), n_aceptadas=Count('id', filter=aceptada),
                monto=Sum('monto_total'), monto_aceptado=Sum('monto_total', filter=aceptada),
            )
        }
        proyectos = dict(Proyecto.objects.values_list('cliente_id').annotate(n=Count('id')))
        informes = dict(
            InformeFinal.objects.values_list('solicitud__cotizacion__cliente_id').annotate(n=Count('id'))
        )
        origenes = dict(Cliente.ORIGEN_CHOICES)
        etiquetas_origen = {'lims': 'LIMS', 'web': 'Web'}

        for c in qs.order_by('razon_social').values('id', 'razon_social', 'origen', 'activo', 'creado_en'):
            cot = cotizaciones.get(c['id'], {})
            alta = timezone.localtime(c['creado_en']) if c['creado_en'] else None
            yield {
                'razon_social': c['razon_social'],
                'origen': etiquetas_origen.get(c['origen'], origenes.get(c['origen'], c['origen'])),
                'activo': _si_no(c['activo']),
                'anio': _anio(alta),
                'mes': _mes(alta),
                'n_cotizaciones': cot.get('n', 0),
                'n_aceptadas': cot.get('n_aceptadas', 0),
                'monto': _num(cot.get('monto')),
                'monto_aceptado': _num(cot.get('monto_aceptado')),
                'n_proyectos': proyectos.get(c['id'], 0),
                'n_informes': informes.get(c['id'], 0),
            }


CONJUNTOS = {c.clave: c for c in (Cotizaciones(), ItemsCotizados(), Clientes())}


def conjuntos_para(user):
    return [c for c in CONJUNTOS.values() if c.puede_ver(user)]
