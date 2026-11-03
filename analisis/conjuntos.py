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
from datetime import timedelta
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

    def registros(self, qs, desde=None, hasta=None):
        """Itera dicts con las claves de `campos`. Puede traer claves de más:
        `datos()` solo copia las de la lista blanca."""
        raise NotImplementedError

    def datos(self, user, desde=None, hasta=None):
        qs = self.filtrar_fechas(self.queryset(), desde, hasta)
        total = qs.count()
        if total > LIMITE_FILAS:
            raise FilasExcedidas(total)
        campos = self.campos_visibles(user)
        filas = [[registro.get(c.clave) for c in campos] for registro in self.registros(qs, desde, hasta)]
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

    def registros(self, qs, desde=None, hasta=None):
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

    def registros(self, qs, desde=None, hasta=None):
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

    def registros(self, qs, desde=None, hasta=None):
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



# ----------------------------------------------------------------------
# Laboratorio: recepción, ensayos, informes, proyectos, agenda y web (PR 2)
# ----------------------------------------------------------------------

VER_CLIENTE_EN_ENSAYOS = 'ensayos.ver_todos'


def _dias(desde, hasta):
    if not desde or not hasta:
        return None
    return (hasta - desde).days


def _atraso(programada, real, hoy):
    """CA-06.8: contra la fecha real si existe; si no, contra hoy. Nunca negativo."""
    if not programada:
        return 0
    return max((real or hoy) - programada, timedelta(0)).days


def _fecha_local(valor):
    return timezone.localtime(valor).date() if valor else None


def _nombre_usuario(nombre_perfil, username):
    return nombre_perfil or username or 'Sin asignar'


class Muestras(Conjunto):
    clave = 'muestras'
    nombre = 'Muestras recibidas'
    modulo = 'Recepción'
    descripcion = 'Una fila por muestra recibida. El rango filtra por fecha de recepción.'
    permiso = 'muestras.ver'
    campo_fecha = 'recepcion__fecha_recepcion__date'
    campos = (
        Campo('codigo', 'Código de laboratorio'),
        Campo('numero', 'N.º oferta'),
        Campo('cliente', 'Cliente'),
        Campo('tipo', 'Tipo de muestra'),
        Campo('unidad', 'Unidad'),
        Campo('procedencia', 'Procedencia'),
        Campo('recibido_por', 'Recibido por'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('cantidad', 'Cantidad', NUMERO),
        Campo('masa', 'Masa aprox.', NUMERO),
        Campo('dias_programado', 'Días recepción → ensayo programado', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Muestras por tipo y mes', 'rows': ['Tipo de muestra'], 'cols': ['Mes'],
         'aggregatorName': 'Suma', 'vals': ['Cantidad'], 'rendererName': 'Tabla'},
        {'nombre': 'Muestras por cliente', 'rows': ['Cliente'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['Cantidad'], 'rendererName': 'Barras', 'rowOrder': 'value_z_to_a'},
    )

    def queryset(self):
        from proyectos.models import MuestraDetalle
        return MuestraDetalle.objects.all()

    def registros(self, qs, desde=None, hasta=None):
        valores = qs.order_by('recepcion__fecha_recepcion', 'id').values(
            'codigo_laboratorio', 'recepcion__cotizacion__numero_oferta',
            'recepcion__cotizacion__cliente__razon_social', 'tipo_muestra__nombre', 'unidad_medida__nombre',
            'recepcion__procedencia', 'recepcion__responsable_recepcion__trabajadorprofile__nombre_completo',
            'recepcion__responsable_recepcion__username', 'recepcion__fecha_recepcion',
            'recepcion__fecha_ensayo_programado', 'cantidad', 'masa_aprox',
        )
        for v in valores:
            recibida = _fecha_local(v['recepcion__fecha_recepcion'])
            yield {
                'codigo': v['codigo_laboratorio'] or '',
                'numero': v['recepcion__cotizacion__numero_oferta'] or 'S/N',
                'cliente': v['recepcion__cotizacion__cliente__razon_social'] or '',
                'tipo': v['tipo_muestra__nombre'] or '',
                'unidad': v['unidad_medida__nombre'] or 'Sin unidad',
                'procedencia': v['recepcion__procedencia'] or '',
                'recibido_por': _nombre_usuario(
                    v['recepcion__responsable_recepcion__trabajadorprofile__nombre_completo'],
                    v['recepcion__responsable_recepcion__username']),
                'anio': _anio(recibida),
                'mes': _mes(recibida),
                'cantidad': _num(v['cantidad']),
                'masa': _num(v['masa_aprox']),
                'dias_programado': _dias(recibida, v['recepcion__fecha_ensayo_programado']),
            }


class Solicitudes(Conjunto):
    clave = 'solicitudes'
    nombre = 'Solicitudes de ensayo'
    modulo = 'Ensayos'
    descripcion = 'Una fila por solicitud. Vencida = sin finalizar y con entrega programada anterior a hoy.'
    permiso = 'ensayos.ver'
    campo_fecha = 'fecha_solicitud'
    campos = (
        Campo('codigo', 'Código de solicitud'),
        Campo('numero', 'N.º oferta'),
        Campo('cliente', 'Cliente', permiso=VER_CLIENTE_EN_ENSAYOS),
        Campo('estado', 'Estado'),
        Campo('elaborado', 'Elaborado por'),
        Campo('revisado', 'Revisado por'),
        Campo('vencida', 'Vencida'),
        Campo('con_incidencias', 'Con incidencias'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('n_ensayos', 'N.º ensayos', NUMERO),
        Campo('n_incidencias', 'N.º incidencias', NUMERO),
        Campo('atraso', 'Días de atraso', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Solicitudes por estado y mes', 'rows': ['Mes'], 'cols': ['Estado'],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Barras apiladas'},
        {'nombre': 'Vencidas por elaborador', 'rows': ['Elaborado por'], 'cols': [],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Tabla',
         'inclusions': {'Vencida': ['Sí']}, 'rowOrder': 'value_z_to_a'},
    )

    def queryset(self):
        from proyectos.models import SolicitudEnsayo
        return SolicitudEnsayo.objects.all()

    def registros(self, qs, desde=None, hasta=None):
        from proyectos.models import SolicitudEnsayo
        hoy = timezone.localdate()
        estados = dict(SolicitudEnsayo.ESTADOS)
        valores = qs.order_by('fecha_solicitud', 'id').annotate(
            n_ensayos=Count('detalles', distinct=True), n_incidencias=Count('incidencias', distinct=True),
        ).values(
            'codigo_solicitud', 'cotizacion__numero_oferta', 'cotizacion__cliente__razon_social', 'estado',
            'elaborado_por__nombre_completo', 'revisado_por__nombre_completo', 'fecha_solicitud',
            'fecha_entrega_programada', 'fecha_entrega_real', 'n_ensayos', 'n_incidencias',
        )
        for v in valores:
            programada, real = v['fecha_entrega_programada'], v['fecha_entrega_real']
            abierta = v['estado'] != 'finalizado'
            vencida = abierta and programada is not None and programada < hoy
            yield {
                'codigo': v['codigo_solicitud'] or '',
                'numero': v['cotizacion__numero_oferta'] or 'S/N',
                'cliente': v['cotizacion__cliente__razon_social'] or '',
                'estado': estados.get(v['estado'], v['estado']).capitalize(),
                'elaborado': v['elaborado_por__nombre_completo'] or 'Sin asignar',
                'revisado': v['revisado_por__nombre_completo'] or 'Sin revisar',
                'vencida': _si_no(vencida),
                'con_incidencias': _si_no(v['n_incidencias']),
                'anio': _anio(v['fecha_solicitud']),
                'mes': _mes(v['fecha_solicitud']),
                'n_ensayos': v['n_ensayos'],
                'n_incidencias': v['n_incidencias'],
                # Finalizada sin fecha real: no se cuenta atraso contra hoy.
                'atraso': 0 if not abierta and real is None else _atraso(programada, real, hoy),
            }


class EnsayosAsignados(Conjunto):
    clave = 'ensayos'
    nombre = 'Ensayos asignados'
    modulo = 'Ensayos'
    descripcion = ('Una fila por ensayo de una solicitud. El rango filtra por entrega programada. '
                   'Terminado = tiene fecha real de entrega (RN-R05).')
    permiso = 'ensayos.ver'
    campo_fecha = 'fecha_entrega_programada'
    campos = (
        Campo('ensayo', 'Ensayo'),
        Campo('norma', 'Norma'),
        Campo('tecnico', 'Técnico'),
        Campo('muestra', 'Código de muestra'),
        Campo('solicitud', 'Código de solicitud'),
        Campo('cliente', 'Cliente', permiso=VER_CLIENTE_EN_ENSAYOS),
        Campo('aceptado', 'Aceptado por técnico'),
        Campo('terminado', 'Terminado'),
        Campo('a_tiempo', 'A tiempo'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('atraso', 'Días de atraso', NUMERO),
        Campo('ejecucion', 'Días de ejecución', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Ensayos por técnico a tiempo o atrasados', 'rows': ['Técnico'], 'cols': ['A tiempo'],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Barras apiladas'},
        {'nombre': 'Atraso promedio por ensayo', 'rows': ['Ensayo'], 'cols': [],
         'aggregatorName': 'Promedio', 'vals': ['Días de atraso'], 'rendererName': 'Tabla',
         'rowOrder': 'value_z_to_a'},
    )

    def queryset(self):
        from proyectos.models import DetalleSolicitudEnsayo
        return DetalleSolicitudEnsayo.objects.all()

    def registros(self, qs, desde=None, hasta=None):
        hoy = timezone.localdate()
        valores = qs.order_by('fecha_entrega_programada', 'id').values(
            'descripcion_ensayo', 'norma', 'tecnico_asignado__nombre_completo', 'muestra__codigo_laboratorio',
            'solicitud__codigo_solicitud', 'solicitud__cotizacion__cliente__razon_social', 'aceptado_tecnico',
            'fecha_entrega_programada', 'fecha_entrega_real', 'solicitud__fecha_solicitud',
        )
        for v in valores:
            programada, real = v['fecha_entrega_programada'], v['fecha_entrega_real']
            if real is None:
                a_tiempo = 'Pendiente'
            else:
                a_tiempo = 'Sí' if programada is None or real <= programada else 'No'
            yield {
                'ensayo': v['descripcion_ensayo'] or '',
                'norma': v['norma'] or '',
                'tecnico': v['tecnico_asignado__nombre_completo'] or 'Sin asignar',
                'muestra': v['muestra__codigo_laboratorio'] or '',
                'solicitud': v['solicitud__codigo_solicitud'] or '',
                'cliente': v['solicitud__cotizacion__cliente__razon_social'] or '',
                'aceptado': _si_no(v['aceptado_tecnico']),
                'terminado': _si_no(real),
                'a_tiempo': a_tiempo,
                'anio': _anio(programada),
                'mes': _mes(programada),
                'atraso': _atraso(programada, real, hoy),
                'ejecucion': _dias(v['solicitud__fecha_solicitud'], real),
            }


class Incidencias(Conjunto):
    clave = 'incidencias'
    nombre = 'Incidencias'
    modulo = 'Ensayos'
    descripcion = 'Una fila por incidencia registrada en una solicitud.'
    permiso = 'ensayos.ver'
    campo_fecha = 'fecha_ocurrencia__date'
    rango_defecto = 'todo'
    campos = (
        Campo('solicitud', 'Código de solicitud'),
        Campo('cliente', 'Cliente', permiso=VER_CLIENTE_EN_ENSAYOS),
        Campo('representante', 'Representante del laboratorio'),
        Campo('autorizada', 'Autorizada'),
        Campo('autorizado_por', 'Autorizado por'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('dias_autorizacion', 'Días hasta autorización', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Incidencias por mes y autorización', 'rows': ['Mes'], 'cols': ['Autorizada'],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Barras apiladas'},
    )

    def queryset(self):
        from proyectos.models import IncidenciaSolicitud
        return IncidenciaSolicitud.objects.all()

    def registros(self, qs, desde=None, hasta=None):
        valores = qs.order_by('fecha_ocurrencia', 'id').values(
            'solicitud__codigo_solicitud', 'solicitud__cotizacion__cliente__razon_social',
            'representante_laboratorio__nombre_completo', 'esta_autorizada', 'autorizado_por__nombre_completo',
            'fecha_ocurrencia', 'fecha_autorizacion',
        )
        for v in valores:
            ocurrio = _fecha_local(v['fecha_ocurrencia'])
            yield {
                'solicitud': v['solicitud__codigo_solicitud'] or '',
                'cliente': v['solicitud__cotizacion__cliente__razon_social'] or '',
                'representante': v['representante_laboratorio__nombre_completo'] or 'Sin asignar',
                'autorizada': _si_no(v['esta_autorizada']),
                'autorizado_por': v['autorizado_por__nombre_completo'] or '—',
                'anio': _anio(ocurrio),
                'mes': _mes(ocurrio),
                'dias_autorizacion': _dias(ocurrio, _fecha_local(v['fecha_autorizacion'])),
            }


class Informes(Conjunto):
    clave = 'informes'
    nombre = 'Informes finales'
    modulo = 'Informes'
    descripcion = 'Una fila por informe final emitido. El rango filtra por fecha de emisión.'
    permiso = 'informes.ver'
    campo_fecha = 'fecha_emision__date'
    campos = (
        Campo('codigo', 'Código de informe'),
        Campo('solicitud', 'Código de solicitud'),
        Campo('cliente', 'Cliente'),
        Campo('estado_envio', 'Estado de envío'),
        Campo('firmado_por', 'Firmado por'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('descargas', 'Descargas', NUMERO),
        Campo('dias_envio', 'Días emisión → envío', NUMERO),
        Campo('dias_emision', 'Días solicitud → emisión', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Pendientes de envío por cliente', 'rows': ['Cliente'], 'cols': [],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Tabla',
         'inclusions': {'Estado de envío': ['Pendiente de Envío']}, 'rowOrder': 'value_z_to_a'},
        {'nombre': 'Informes por mes y estado de envío', 'rows': ['Mes'], 'cols': ['Estado de envío'],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Barras apiladas'},
    )

    def queryset(self):
        from proyectos.models import InformeFinal
        return InformeFinal.objects.all()

    def registros(self, qs, desde=None, hasta=None):
        from proyectos.models import InformeFinal
        estados = dict(InformeFinal.ESTADOS_ENVIO)
        valores = qs.order_by('fecha_emision', 'id').values(
            'codigo_informe', 'solicitud__codigo_solicitud', 'solicitud__cotizacion__cliente__razon_social',
            'estado_envio', 'responsable_firma__nombre_completo', 'fecha_emision', 'fecha_envio',
            'descargas_count', 'solicitud__fecha_solicitud',
        )
        for v in valores:
            emitido = _fecha_local(v['fecha_emision'])
            yield {
                'codigo': v['codigo_informe'] or '',
                'solicitud': v['solicitud__codigo_solicitud'] or '',
                'cliente': v['solicitud__cotizacion__cliente__razon_social'] or '',
                'estado_envio': estados.get(v['estado_envio'], v['estado_envio']),
                'firmado_por': v['responsable_firma__nombre_completo'] or '',
                'anio': _anio(emitido),
                'mes': _mes(emitido),
                'descargas': v['descargas_count'],
                'dias_envio': _dias(emitido, _fecha_local(v['fecha_envio'])),
                'dias_emision': _dias(v['solicitud__fecha_solicitud'], emitido),
            }


class Proyectos(Conjunto):
    clave = 'proyectos'
    nombre = 'Proyectos'
    modulo = 'Proyectos'
    descripcion = ('Una fila por proyecto. El rango filtra por fecha de inicio. Vencido = entrega estimada '
                   'anterior a hoy y sin finalizar ni cancelar (RN-R06).')
    permiso = 'proyectos.ver'
    campo_fecha = 'fecha_inicio'
    campos = (
        Campo('codigo', 'Código de proyecto'),
        Campo('cliente', 'Cliente'),
        Campo('estado', 'Estado'),
        Campo('vencido', 'Vencido'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('previstas', 'Muestras previstas', NUMERO),
        Campo('registradas', 'Muestras registradas', NUMERO),
        Campo('avance', '% avance de muestras', NUMERO),
        Campo('atraso', 'Días de atraso', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Proyectos por estado', 'rows': ['Estado'], 'cols': [],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Barras'},
        {'nombre': 'Vencidos por cliente', 'rows': ['Cliente'], 'cols': [],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Tabla',
         'inclusions': {'Vencido': ['Sí']}, 'rowOrder': 'value_z_to_a'},
    )

    def queryset(self):
        from proyectos.models import Proyecto
        return Proyecto.objects.all()

    def registros(self, qs, desde=None, hasta=None):
        from proyectos.models import Proyecto
        hoy = timezone.localdate()
        estados = dict(Proyecto.ESTADOS_PROYECTO)
        valores = qs.order_by('fecha_inicio', 'id').values(
            'codigo_proyecto', 'cliente__razon_social', 'estado', 'fecha_inicio', 'fecha_entrega_estimada',
            'numero_muestras', 'numero_muestras_registradas',
        )
        for v in valores:
            abierto = v['estado'] not in ('FINALIZADO', 'CANCELADO')
            entrega = v['fecha_entrega_estimada']
            vencido = abierto and entrega is not None and entrega < hoy
            previstas = v['numero_muestras'] or 0
            registradas = v['numero_muestras_registradas'] or 0
            yield {
                'codigo': v['codigo_proyecto'],
                'cliente': v['cliente__razon_social'] or '',
                'estado': estados.get(v['estado'], v['estado']),
                'vencido': _si_no(vencido),
                'anio': _anio(v['fecha_inicio']),
                'mes': _mes(v['fecha_inicio']),
                'previstas': previstas,
                'registradas': registradas,
                'avance': round(100 * registradas / previstas, 1) if previstas else 0,
                'atraso': _atraso(entrega, None, hoy) if vencido else 0,
            }


class Actividades(Conjunto):
    clave = 'actividades'
    nombre = 'Actividades de la agenda'
    modulo = 'Agenda'
    descripcion = 'Una fila por actividad del calendario. El rango filtra por fecha de inicio.'
    permiso = 'calendario.ver'
    campo_fecha = 'fecha_inicio__date'
    campos = (
        Campo('tipo', 'Origen'),
        Campo('clase', 'Clase'),
        Campo('estado', 'Estado'),
        Campo('prioridad', 'Prioridad'),
        Campo('categoria', 'Categoría'),
        Campo('cliente', 'Cliente'),
        Campo('creada_por', 'Creada por'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('duracion', 'Duración (h)', NUMERO),
        Campo('atraso', 'Días de atraso', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Actividades por clase y estado', 'rows': ['Clase'], 'cols': ['Estado'],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Tabla'},
        {'nombre': 'Horas por mes', 'rows': ['Mes'], 'cols': [],
         'aggregatorName': 'Suma', 'vals': ['Duración (h)'], 'rendererName': 'Líneas'},
    )

    def queryset(self):
        from actividades.models import CalendarioActividad
        return CalendarioActividad.objects.all()

    def registros(self, qs, desde=None, hasta=None):
        from actividades.models import CalendarioActividad as A
        tipos, clases = dict(A.TIPO_ACTIVIDAD), dict(A.CLASE_ACTIVIDAD)
        estados, prioridades = dict(A.ESTADO_ACTIVIDAD), dict(A.PRIORIDAD)
        hoy = timezone.localdate()
        valores = qs.order_by('fecha_inicio', 'id').values(
            'tipo', 'clase', 'estado', 'prioridad', 'categoria__nombre', 'cliente__razon_social',
            'cliente_nombre_manual', 'creado_por__trabajadorprofile__nombre_completo', 'creado_por__username',
            'fecha_inicio', 'fecha_fin',
        )
        for v in valores:
            inicio, fin = v['fecha_inicio'], v['fecha_fin']
            duracion = round((fin - inicio).total_seconds() / 3600, 2) if inicio and fin and fin > inicio else 0
            abierta = v['estado'] not in ('COMPLETADA', 'CANCELADA')
            dia = _fecha_local(inicio)
            yield {
                'tipo': tipos.get(v['tipo'], v['tipo']),
                'clase': clases.get(v['clase'], v['clase']),
                'estado': estados.get(v['estado'], v['estado']),
                'prioridad': prioridades.get(v['prioridad'], v['prioridad']),
                'categoria': v['categoria__nombre'] or 'Sin categoría',
                'cliente': v['cliente__razon_social'] or v['cliente_nombre_manual'] or 'Sin cliente',
                'creada_por': _nombre_usuario(v['creado_por__trabajadorprofile__nombre_completo'],
                                              v['creado_por__username']),
                'anio': _anio(dia),
                'mes': _mes(dia),
                'duracion': duracion,
                'atraso': _atraso(_fecha_local(fin), None, hoy) if abierta and fin else 0,
            }


class BandejaWeb(Conjunto):
    """Mensajes de contacto y solicitudes de cotización de la web. Sin datos
    personales: ni nombre, ni correo, ni teléfono, ni RUC, ni texto del mensaje."""
    clave = 'bandeja-web'
    nombre = 'Bandeja web'
    modulo = 'Web'
    descripcion = 'Una fila por mensaje de contacto o solicitud de cotización llegada desde la web.'
    permiso = 'cotizaciones.ver'
    campo_fecha = 'creado__date'
    campos = (
        Campo('tipo', 'Tipo'),
        Campo('origen', 'Página de origen'),
        Campo('estado', 'Estado'),
        Campo('convertida', 'Convertida en cotización'),
        Campo('anio', 'Año'),
        Campo('mes', 'Mes'),
        Campo('n_items', 'N.º ítems', NUMERO),
        Campo('dias_atencion', 'Días hasta atención', NUMERO),
    )
    vistas_rapidas = (
        {'nombre': 'Llegadas por mes y tipo', 'rows': ['Mes'], 'cols': ['Tipo'],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Barras apiladas'},
        {'nombre': 'Páginas que más convierten', 'rows': ['Página de origen'], 'cols': ['Tipo'],
         'aggregatorName': 'Cantidad', 'vals': [], 'rendererName': 'Tabla', 'rowOrder': 'value_z_to_a'},
    )

    def queryset(self):
        from web_contacto.models import MensajeContacto
        return MensajeContacto.objects.all()

    def _solicitudes(self, desde, hasta):
        from web_contacto.models import SolicitudCotizacionWeb
        qs = SolicitudCotizacionWeb.objects.all()
        if desde:
            qs = qs.filter(creado__date__gte=desde)
        if hasta:
            qs = qs.filter(creado__date__lte=hasta)
        return qs

    def filtrar_fechas(self, qs, desde, hasta):
        qs = super().filtrar_fechas(qs, desde, hasta)
        total = qs.count() + self._solicitudes(desde, hasta).count()
        if total > LIMITE_FILAS:
            raise FilasExcedidas(total)
        return qs

    def registros(self, qs, desde=None, hasta=None):
        from web_contacto.models import ESTADO_CHOICES
        estados = dict(ESTADO_CHOICES)
        for v in qs.order_by('creado', 'id').values('origen', 'estado', 'creado', 'fecha_atencion'):
            dia = _fecha_local(v['creado'])
            yield {
                'tipo': 'Mensaje de contacto',
                'origen': v['origen'] or 'Sin dato',
                'estado': estados.get(v['estado'], v['estado']),
                'convertida': 'No aplica',
                'anio': _anio(dia),
                'mes': _mes(dia),
                'n_items': 0,
                'dias_atencion': _dias(dia, _fecha_local(v['fecha_atencion'])),
            }
        solicitudes = self._solicitudes(desde, hasta).order_by('creado', 'id').annotate(
            n_items=Count('items'),
        ).values('origen', 'creado', 'cotizacion__estado', 'n_items')
        for v in solicitudes:
            dia = _fecha_local(v['creado'])
            yield {
                'tipo': 'Solicitud de cotización',
                'origen': v['origen'] or 'Sin dato',
                'estado': f"Cotización {v['cotizacion__estado'].lower()}" if v['cotizacion__estado'] else 'Sin cotización',
                'convertida': _si_no(v['cotizacion__estado']),
                'anio': _anio(dia),
                'mes': _mes(dia),
                'n_items': v['n_items'],
                'dias_atencion': None,
            }


CONJUNTOS = {c.clave: c for c in (
    Cotizaciones(), ItemsCotizados(), Clientes(), Muestras(), Solicitudes(), EnsayosAsignados(),
    Incidencias(), Informes(), Proyectos(), Actividades(), BandejaWeb(),
)}


def conjuntos_para(user):
    return [c for c in CONJUNTOS.values() if c.puede_ver(user)]
