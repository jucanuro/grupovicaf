"""Informe de compresión de probetas armado por el sistema (HU-LIMS-16) y su
exportación a Excel (HU-LIMS-18).

El PDF replica el informe real VCF-INF-2026-4582: carátula (VCF-LAB-FOR-064)
con cliente, proyecto, línea de tiempo, Tabla 01 de ítems y Tabla 02 de
métodos, notas y QR; luego una página por probeta (VCF-LAB-FOR-039) con
condiciones ambientales, datos, resultados, las cinco fotos, fractura y
equipos; y «Fin del Informe». Es un documento privado del laboratorio para su
cliente: lleva sus datos de contacto (no pasa por la página pública del QR).
"""
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from .models import DetalleSolicitudEnsayo, ResultadoEnsayo, FotoEnsayo, Proyecto, SesionEnsayo
from .views_compresion import FILTRO_COMPRESION

FORMATO_CARATULA = {'codigo': 'VCF-LAB-FOR-064', 'fecha': '2026-05-22', 'version': '12', 'aprobacion': 'JL'}
FORMATO_PROBETA = {'codigo': 'VCF-LAB-FOR-039', 'fecha': '2026-05-22', 'version': '17', 'aprobacion': 'JL'}

NOTAS_ITEMS = [
    "GRUPO VICAF SAC. no ha participado en la etapa de muestreo, esta ha sido realizada por el cliente.",
    "El proceso de curado ha sido desarrollado en las instalaciones del Laboratorio desde el día de "
    "recepción hasta el día de ensayo.",
    "No se almacena contramuestra por ser un ensayo destructivo.",
]

NOTAS = [
    "(*) Información proporcionada por el cliente.",
    "El Laboratorio de ensayos de Grupo VICAF SAC cuenta con un Sistema de Gestión de Calidad que cumple "
    "con los requisitos de la norma NTP ISO/IEC 17025-2017.",
    "Los informes tienen validez únicamente si incluyen la firma y sello del profesional responsable.",
    "El presente informe no puede ser difundido de manera parcial, ni se aceptan modificaciones en los "
    "resultados reportados.",
    "Los ensayos indicados en la Tabla No. 02 han sido realizados en el Laboratorio de Grupo VICAF S.A.C., "
    "ubicado en {direccion}, de acuerdo con las normas estandarizadas señaladas, sin aplicar adiciones, "
    "desviaciones o exclusiones respecto a los métodos de ensayo.",
    "Los resultados emitidos no deben ser utilizados como certificación de conformidad con normas de "
    "producto o certificado del sistema de calidad de la entidad que lo produce.",
    "El reporte de Incertidumbre de Medición, no fue solicitado por el cliente.",
]

ANEXOS = [
    "Los resultados emitidos en el presente informe se relacionan solamente con los ítems sometidos a "
    "ensayo, tal como se recibieron.",
    "El Laboratorio es responsable de toda la información suministrada en el informe excepto de la "
    "información suministrada por el cliente que pueda afectar a la validez de los resultados.",
    "Este laboratorio está acreditado de acuerdo con la norma internacional reconocida NTP-ISO/IEC "
    "17025:2017. Esta acreditación demuestra la competencia técnica para un alcance definido y el "
    "funcionamiento de un sistema de gestión de calidad de laboratorio.",
    "Este informe de ensayo, al estar en el marco de la acreditación del INACAL – DA, se encuentran dentro "
    "del ámbito de reconocimiento multilateral/mutuo de los miembros firmantes de IAAC e ILAC.",
    "Los resultados de los ensayos realizados a las muestras indicadas se anexan al presente informe.",
]

# ASTM C39/C39M-26, figura de fracturas típicas (DP-LIMS-19 A).
FRACTURAS = [
    (1, "Conos razonablemente bien formados en ambos extremos, menos de 1 in. de agrietamiento a través de las tapas."),
    (2, "Cono bien formado en un extremo, grietas verticales que atraviesan las tapas, cono no bien definido en el otro extremo."),
    (3, "Agrietamiento vertical columnar en ambos extremos, sin conos bien formados."),
    (4, "Fractura diagonal sin agrietamiento en los extremos; golpee con un martillo para distinguir del Tipo 1."),
    (5, "Fracturas laterales en la parte superior o inferior (ocurren comúnmente con tapas no adheridas)."),
    (6, "Similar al tipo 5 pero el extremo del cilindro es puntiagudo."),
]


class InformeIncompleto(Exception):
    pass


def lineas_resultados(solicitud):
    """Todas las líneas de la solicitud, con su resultado (cualquier plantilla)."""
    return (
        DetalleSolicitudEnsayo.objects.filter(solicitud=solicitud)
        .select_related('muestra', 'resultado', 'resultado__tecnico',
                        'resultado__sesion', 'tecnico_asignado')
        .order_by('muestra__nro_item', 'muestra__codigo_laboratorio')
    )


def lineas_compresion(solicitud):
    return (
        DetalleSolicitudEnsayo.objects.filter(FILTRO_COMPRESION, solicitud=solicitud)
        .select_related('muestra', 'resultado', 'resultado__tecnico',
                        'resultado__sesion', 'tecnico_asignado')
        .order_by('muestra__nro_item', 'muestra__codigo_laboratorio')
    )


def _negocio():
    from siteconfig.models import NegocioConfig
    return NegocioConfig.objects.first()


def _uri(field):
    """file:// de un archivo local para WeasyPrint, o '' si no existe."""
    try:
        ruta = Path(field.path)
    except (ValueError, NotImplementedError, AttributeError):
        return ''
    return ruta.as_uri() if ruta.exists() else ''


def contexto_informe(informe):
    solicitud = informe.solicitud
    recepcion = solicitud.recepcion
    cotizacion = solicitud.cotizacion
    cliente = cotizacion.cliente
    proyecto = Proyecto.objects.filter(cotizacion=cotizacion).only('nombre_proyecto').first()

    probetas = []
    for detalle in lineas_compresion(solicitud):
        ensayo = getattr(detalle, 'resultado', None)
        if ensayo is None or not ensayo.aprobado:
            raise InformeIncompleto(f"La probeta {detalle.muestra.codigo_laboratorio} no está aprobada.")
        fotos = {f.tipo: _uri(f.imagen) for f in ensayo.fotos.all()}
        sesion = ensayo.sesion
        equipos = []
        if sesion:
            etiquetas = {'prensa': 'ID Prensa', 'balanza': 'ID Balanza', 'vernier': 'ID Vernier',
                         'termohigrometro': 'ID Termohigrómetro', 'cuna': 'ID Cuña', 'escuadra': 'ID Escuadra'}
            equipos = [(etiquetas[c], getattr(sesion, c).codigo) for c, _ in SesionEnsayo.EQUIPOS]
        probetas.append({
            'detalle': detalle,
            'muestra': detalle.muestra,
            'ensayo': ensayo,
            'sesion': sesion,
            'equipos': equipos,
            'foto': fotos,
        })
    if not probetas:
        raise InformeIncompleto("La solicitud no tiene probetas de compresión.")

    fechas_ensayo = sorted({p['ensayo'].fecha_ensayo for p in probetas if p['ensayo'].fecha_ensayo})
    solicitadas = sorted({p['muestra'].fecha_ensayo_solicitada for p in probetas if p['muestra'].fecha_ensayo_solicitada})
    fabricaciones = sorted({p['muestra'].fecha_fabricacion for p in probetas if p['muestra'].fecha_fabricacion})
    negocio = _negocio()
    direccion = (
        f"{negocio.direccion_calle} - {negocio.direccion_localidad}" if negocio else "Jr. Los Topacios 440 - Cajamarca"
    )
    normas = {}
    for p in probetas:
        normas.setdefault(p['detalle'].norma, 0)
        normas[p['detalle'].norma] += 1

    firmante = informe.responsable_firma
    return {
        'informe': informe,
        'negocio': negocio,
        'direccion_laboratorio': direccion,
        'cliente': {
            'razon_social': cliente.razon_social,
            'ruc': cliente.ruc,
            'direccion': cliente.direccion or '-',
            'sitio_web': getattr(cliente, 'sitio_web', '') or '-',
            'contacto': cotizacion.persona_contacto or cliente.persona_contacto or '-',
            'cargo': getattr(cliente, 'cargo_contacto', '') or '-',
            'celular': cotizacion.telefono_contacto or cliente.celular_contacto or '-',
            'correo': cotizacion.correo_contacto or cliente.correo_contacto or '-',
        },
        'proyecto': (proyecto.nombre_proyecto if proyecto else '') or cotizacion.proyecto_asociado or '-',
        'ubicacion': recepcion.ubicacion_informe or '-',
        'linea_tiempo': {
            'solicitada': solicitadas[0] if solicitadas else None,
            'ejecucion': fechas_ensayo,
            'recepcion': timezone.localtime(recepcion.fecha_recepcion).date() if recepcion.fecha_recepcion else None,
            'fabricacion': fabricaciones,
            'emision': timezone.localtime(informe.fecha_emision).date(),
        },
        'metodos': [
            {'nombre': 'Standard Test Method for Compressive Strength of Cylindrical Concrete Specimens',
             'norma': norma, 'cantidad': cantidad}
            for norma, cantidad in normas.items()
        ],
        'probetas': probetas,
        'fotos_tipos': FotoEnsayo.tipos_de(ResultadoEnsayo.PLANTILLA_COMPRESION),
        'fracturas': FRACTURAS,
        'notas_items': NOTAS_ITEMS,
        'notas': [n.format(direccion=direccion) for n in NOTAS],
        'anexos': ANEXOS,
        'qr': _uri(informe.qr_code) if informe.qr_code else '',
        'firmante': {
            'nombre': firmante.get_nombre_formal() if firmante else '',
            'cargo': firmante.rol.nombre if firmante and firmante.rol_id else 'Jefe de Laboratorio',
            'firma': _uri(firmante.firma_electronica) if firmante and firmante.firma_electronica else '',
        },
        'logo': (Path(settings.BASE_DIR) / 'static' / 'img' / 'LogoF.png').as_uri(),
        'formato_caratula': FORMATO_CARATULA,
        'formato_probeta': FORMATO_PROBETA,
        'total_paginas': 1 + len(probetas),
    }


def generar_pdf(informe):
    from weasyprint import HTML
    html = render_to_string('proyectos/informe_compresion_pdf.html', contexto_informe(informe))
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


# --- Excel (HU-LIMS-18) ------------------------------------------------------

COLUMNAS_EXCEL = [
    ('Solicitud', None), ('ID laboratorio', None), ('ID cliente', None), ('Elemento estructural', None),
    ("f'c (kg/cm²)", '0'), ('Fabricación', 'yyyy-mm-dd'), ('Fecha de ensayo', 'yyyy-mm-dd'), ('Edad (días)', '0'),
    ('Masa (g)', '0.0'), ('D1 (mm)', '0.00'), ('D2 (mm)', '0.00'), ('L1 (mm)', '0.00'), ('L2 (mm)', '0.00'),
    ('L3 (mm)', '0.00'), ('Carga máxima (kN)', '0.00'), ('Diámetro prom. (mm)', '0.00'),
    ('Longitud prom. (mm)', '0.00'), ('Área (mm²)', '0.00'), ('L/D', '0.00'), ('Factor', '0.00'),
    ('Resistencia (MPa)', '0.0'), ('Resistencia (kg/cm²)', '0.0'), ('% obtenido', '0'),
    ('Densidad (kg/m³)', '0'), ('Tipo de fractura', '0'), ('T inicial (°C)', '0.00'), ('HR inicial (%)', '0.00'),
    ('T final (°C)', '0.00'), ('HR final (%)', '0.00'), ('Prensa', None), ('Balanza', None), ('Vernier', None),
    ('Termohigrómetro', None), ('Cuña', None), ('Escuadra', None), ('Técnico', None), ('Estado', None),
]


def _num(valor):
    return float(valor) if valor is not None else None


def exportar_excel(ensayos):
    """xlsx con una fila por probeta; los números van como números (CA-18.2)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Compresión'
    hoja.append([c for c, _ in COLUMNAS_EXCEL])
    for celda in hoja[1]:
        celda.font = Font(bold=True)

    for e in ensayos:
        m = e.detalle.muestra
        s = e.sesion
        equipos = [getattr(s, c).codigo if s else '' for c, _ in SesionEnsayo.EQUIPOS]
        hoja.append([
            e.detalle.solicitud.codigo_solicitud, m.codigo_laboratorio, m.codigo_cliente, m.elemento_estructural,
            _num(m.fc_diseno), m.fecha_fabricacion, e.fecha_ensayo, e.edad_dias,
            _num(e.masa_g), _num(e.d1), _num(e.d2), _num(e.l1), _num(e.l2), _num(e.l3), _num(e.carga_kn),
            _num(e.diametro_prom), _num(e.longitud_prom), _num(e.area), _num(e.relacion_ld), _num(e.factor),
            _num(e.resistencia_mpa), _num(e.resistencia_kgcm2), e.porcentaje, e.densidad, e.tipo_fractura,
            _num(s.temperatura_inicial) if s else None, _num(s.humedad_inicial) if s else None,
            _num(s.temperatura_final) if s else None, _num(s.humedad_final) if s else None,
            *equipos,
            e.tecnico.nombre_completo if e.tecnico else '', e.get_estado_display(),
        ])

    for indice, (_, formato) in enumerate(COLUMNAS_EXCEL, start=1):
        letra = hoja.cell(row=1, column=indice).column_letter
        hoja.column_dimensions[letra].width = max(12, len(COLUMNAS_EXCEL[indice - 1][0]) + 2)
        if formato:
            for fila in hoja.iter_rows(min_row=2, min_col=indice, max_col=indice):
                fila[0].number_format = formato
    hoja.freeze_panes = 'C2'

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def ensayos_para_excel(solicitud=None, desde=None, hasta=None):
    qs = (
        ResultadoEnsayo.objects.filter(estado__in=ResultadoEnsayo.ESTADOS_CERRADOS)
        .select_related('detalle__muestra', 'detalle__solicitud', 'tecnico', 'sesion__prensa',
                        'sesion__balanza', 'sesion__vernier', 'sesion__termohigrometro',
                        'sesion__cuna', 'sesion__escuadra')
        .order_by('fecha_ensayo', 'detalle__muestra__codigo_laboratorio')
    )
    if solicitud is not None:
        qs = qs.filter(detalle__solicitud=solicitud)
    if desde:
        qs = qs.filter(fecha_ensayo__gte=desde)
    if hasta:
        qs = qs.filter(fecha_ensayo__lte=hasta)
    return qs
