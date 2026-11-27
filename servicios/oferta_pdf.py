"""PDF de la oferta técnico-económica con el diseño del Word VCF-LAB-FOR-001 v7.

El Word oficial es la referencia: márgenes, cabecera con logo y contactos, el
marco gris con el cuadro naranja, el código del formato girado en el margen
izquierdo con «Página X de Y», las bandas grises de cada sección, la tabla de
ítems (categorías A, B… y subcategorías a, b…), las notas numeradas, las
condiciones con viñetas y grupos, contactos, datos de pago y firmas.

Se arma con WeasyPrint (soporta @page, contadores de página y elementos que se
repiten en cada hoja). Los textos de condiciones salen de la copia guardada en
la cotización (`CotizacionCondicionItem`); lo que va entre {{ }} es un dato que
se debía completar y se imprime sin las llaves.
"""
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.safestring import mark_safe

# Datos del formato (cabecera del Word, versión vigente).
FORMATO = {
    'codigo': 'VCF-LAB-FOR-001',
    'fecha': '2026-11-05',
    'version': '07',
    'aprobacion': 'JL',
}
# Firma «Aprobó» del Word: la Jefa de Laboratorio.
FIRMANTE = {
    'nombre': 'Ing. Jessica Raquel Riojas Ortiz',
    'cargo': 'Jefe de Laboratorio',
    'empresa': 'GRUPO VICAF SAC',
    'firma': 'img/oferta/firma_jefa_laboratorio.png',
}
CONTACTOS = {
    'tecnicos': [
        {'nombre': 'Ing. Jessica Raquel Riojas Ortiz', 'cargo': 'Jefe de Laboratorio',
         'telefono': '938 172 727', 'correo': 'raquel.riojas@grupovicaf.com'},
        {'nombre': 'Ing. Frank Gonzáles Vásquez', 'cargo': 'Supervisor de Laboratorio',
         'telefono': '949 923 568', 'correo': 'frank.gonzales@grupovicaf.com'},
    ],
    'pagos': {'nombre': 'Carmen R. Bernui Escobedo', 'cargo': 'Gerente Administrativo',
              'telefono': '947 946 743', 'correo': 'carmen.bernui@grupovicaf.com'},
}
DATOS_PAGO = [
    ('Razón Social', 'GRUPO VICAF SAC'),
    ('RUC', '20609464632'),
    ('Dirección', 'JR. LOS TOPACIOS 440 – CAJAMARCA'),
    ('Cuenta BCP (Soles)', '24574415288082'),
    ('Cuenta interbancaria (Soles)', '00224517441528808291'),
    ('Cuenta de Detracción (BN)', '00761271644'),
]
CABECERA = {
    'telefono': '+51 964 326 364',
    'correo': 'informes@grupovicaf.com',
    'linkedin': 'GRUPO VICAF SAC',
    'web': 'www.grupovicaf.com',
}
GRUPO_POR_DEFECTO = 'ENSAYOS DE LABORATORIO'

MARCA_EDITABLE = re.compile(r'\{\{\s*(.*?)\s*\}\}', re.S)
ENLACE = re.compile(r'(https?://[^\s,;]+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+)')


def quitar_marcas(texto):
    """{{XX}} → XX: en el PDF no se ve que el dato venía del Word resaltado."""
    return MARCA_EDITABLE.sub(r'\1', texto or '')


def texto_con_enlaces(texto):
    """Escapa y pinta en azul las direcciones web y los correos, como el Word."""
    partes = ENLACE.split(texto)
    html = ''.join(
        f'<span class="enlace">{escape(p)}</span>' if i % 2 else escape(p) for i, p in enumerate(partes)
    )
    return mark_safe(html)


def soles(valor):
    """S/ 1 310,00: separador de miles con espacio y coma decimal (como el Word)."""
    valor = Decimal(valor or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    entero, decimales = f'{valor:.2f}'.split('.')
    signo = '-' if entero.startswith('-') else ''
    entero = entero.lstrip('-')
    grupos = []
    while entero:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    return f"S/ {signo}{' '.join(grupos)},{decimales}"


def _letra(n, mayuscula=True):
    letras = ''
    while n:
        n, r = divmod(n - 1, 26)
        letras = chr(65 + r) + letras
    return letras if mayuscula else letras.lower()


def filas_items(cotizacion):
    """Filas de la tabla de ítems.

    La cotización guarda cada categoría y subcategoría como un `CotizacionGrupo`
    sin decir cuál es cuál: un grupo sin ítems seguido de otros grupos es una
    categoría (A, B…); los que vienen debajo con ítems son subcategorías
    (a, b…). El grupo interno «ENSAYOS DE LABORATORIO» solo se muestra si
    tiene ítems.
    """
    grupos = [g for g in cotizacion.grupos.all().order_by('orden', 'id')]
    items_por_grupo = {g.pk: list(g.detalles_items.all().order_by('id')) for g in grupos}
    # El formulario crea siempre un primer grupo interno; vacío no se muestra.
    if grupos and grupos[0].nombre_grupo == GRUPO_POR_DEFECTO and not items_por_grupo[grupos[0].pk]:
        grupos = grupos[1:]
    filas = []
    n_cat = n_sub = 0
    en_categoria = False
    for i, g in enumerate(grupos):
        items = items_por_grupo[g.pk]
        if not items and i + 1 < len(grupos):
            # Categoría con subcategorías debajo.
            n_cat += 1
            n_sub = 0
            en_categoria = True
            filas.append({'tipo': 'categoria', 'codigo': _letra(n_cat), 'texto': g.nombre_grupo})
            continue
        if en_categoria:
            n_sub += 1
            filas.append({'tipo': 'subcategoria', 'codigo': _letra(n_sub, False), 'texto': g.nombre_grupo})
        else:
            n_cat += 1
            filas.append({'tipo': 'categoria', 'codigo': _letra(n_cat), 'texto': g.nombre_grupo})
        for n, d in enumerate(items, 1):
            servicio = d.servicio
            nombre = servicio.nombre if servicio else d.descripcion_especifica
            extra = d.descripcion_especifica if d.descripcion_especifica and d.descripcion_especifica != nombre else ''
            if extra and ':' in extra and extra.split(':')[-1].strip() == (nombre or '').strip():
                extra = ''  # «CATEGORÍA - SUBCATEGORÍA: nombre» generado por el formulario
            norma = d.norma_manual or (str(servicio.norma) if servicio and servicio.norma_id else '')
            filas.append({
                'tipo': 'item',
                'codigo': f'{n},00',
                'texto': nombre + (' (*)' if servicio and servicio.esta_acreditado and '(*)' not in nombre else ''),
                'extra': extra,
                'norma': norma,
                'unidad': d.unidad_medida or (servicio.unidad_base if servicio else ''),
                'cantidad': f'{d.cantidad:02d}',
                'unitario': soles(d.precio_unitario),
                'parcial': soles(d.total_detalle),
            })
    return filas


def _nodos(items, reemplazar):
    """Ítems seleccionados de un nivel; un grupo se muestra si algo debajo está marcado."""
    salida = []
    for item in items:
        hijos = _nodos(item.children.all().order_by('orden', 'id'), reemplazar)
        texto = quitar_marcas(reemplazar((item.texto_final or '').strip()))
        if item.tipo_nodo == 'grupo':
            if hijos:
                salida.append({'grupo': True, 'texto': texto, 'hijos': hijos})
            continue
        if item.seleccionado and texto:
            salida.append({'grupo': False, 'texto': texto_con_enlaces(texto), 'hijos': hijos})
        elif hijos:
            salida.extend(hijos)
    return salida


def secciones_condiciones(cotizacion, reemplazar):
    """(notas, secciones numeradas desde el 2) a partir de la copia de la cotización."""
    notas, secciones = [], []
    for seccion in cotizacion.condiciones_secciones.all().order_by('orden', 'id'):
        if not seccion.seleccionada:
            continue
        nodos = _nodos(seccion.items.filter(parent__isnull=True).order_by('orden', 'id'), reemplazar)
        if not nodos:
            continue
        es_notas = seccion.tipo == 'notas' or seccion.codigo.upper().startswith('NOTAS') or \
            seccion.titulo.strip().upper().rstrip(':').endswith('NOTAS')
        if es_notas:
            notas.extend(nodos)
        else:
            titulo = re.sub(r'^\s*\d+[.)]\s*', '', seccion.titulo).strip()
            secciones.append({'titulo': titulo, 'nodos': nodos})
    for n, s in enumerate(secciones, 2):
        s['numero'] = n
    return notas, secciones


def _uri_estatico(ruta):
    encontrado = finders.find(ruta)
    return Path(encontrado).as_uri() if encontrado else ''


def contexto(cotizacion, reemplazar):
    notas, secciones = secciones_condiciones(cotizacion, reemplazar)
    ultimo = (secciones[-1]['numero'] if secciones else 1)
    tasa = cotizacion.tasa_igv if cotizacion.tasa_igv is not None else Decimal('0.18')
    subtotal = cotizacion.subtotal or Decimal('0')
    igv = cotizacion.impuesto_igv if cotizacion.impuesto_igv is not None else subtotal * tasa
    total = cotizacion.monto_total if cotizacion.monto_total is not None else subtotal + igv
    return {
        'cotizacion': cotizacion,
        'cliente': cotizacion.cliente,
        'formato': FORMATO,
        'cabecera': CABECERA,
        'firmante': FIRMANTE,
        'contactos': CONTACTOS,
        'datos_pago': DATOS_PAGO,
        'filas': filas_items(cotizacion),
        'subtotal': soles(subtotal),
        'igv': soles(igv),
        'igv_porcentaje': int((tasa * 100).quantize(Decimal('1'))),
        'total': soles(total),
        'notas': notas,
        'qr': _qr_de(cotizacion),
        'secciones': secciones,
        'n_contactos': ultimo + 1,
        'n_datos': ultimo + 2,
        'img': {
            nombre: _uri_estatico(f'img/oferta/{archivo}')
            for nombre, archivo in (('logo', 'logo.png'), ('telefono', 'telefono.png'), ('correo', 'correo.png'),
                                    ('linkedin', 'linkedin.jpg'), ('web', 'web.png'),
                                    ('firma', 'firma_jefa_laboratorio.png'))
        },
    }


def _qr_de(cotizacion):
    if not cotizacion.numero_oferta:
        return ''
    from .qr import qr_data_uri, url_verificacion
    return qr_data_uri(url_verificacion(cotizacion))


def generar_pdf(cotizacion, reemplazar):
    """Bytes del PDF de la oferta."""
    from weasyprint import HTML

    html = render_to_string('servicios/oferta_pdf.html', contexto(cotizacion, reemplazar))
    return HTML(string=html, base_url=str(Path(finders.find('img/oferta/logo.png')).parent)).write_pdf()
