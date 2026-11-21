"""Informe tipo Word dentro del sistema (fase 2).

El editor del navegador (TipTap) guarda un documento JSON. Aquí se valida ese
JSON contra una lista blanca, se arma el borrador inicial de cada solicitud y
se convierte a HTML para la vista previa y el PDF.

Los «bloques de datos» (carátula, resultados, fotos, equipos, firmas) solo
guardan su tipo y su referencia; su contenido se dibuja siempre desde lo
registrado, así el informe no puede contradecir los resultados.
"""
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from .informe_compresion import ANEXOS, FRACTURAS, NOTAS, NOTAS_ITEMS, _negocio, _uri, lineas_resultados
from .models import FotoEnsayo, Proyecto, ResultadoEnsayo, SesionEnsayo

# --- Bloques de datos ---------------------------------------------------------

BLOQUE_CARATULA = 'caratula'
BLOQUE_RESULTADOS = 'resultados'
BLOQUE_FOTOS = 'fotos'
BLOQUE_EQUIPOS = 'equipos'
BLOQUE_FIRMAS = 'firmas'
BLOQUE_NOTAS = 'notas'
TIPOS_BLOQUE = {
    BLOQUE_CARATULA: 'Datos del cliente y del ensayo',
    BLOQUE_RESULTADOS: 'Resultados',
    BLOQUE_FOTOS: 'Registro fotográfico',
    BLOQUE_EQUIPOS: 'Equipos y condiciones ambientales',
    BLOQUE_NOTAS: 'Notas del laboratorio',
    BLOQUE_FIRMAS: 'Firmas',
}
# Bloques que llevan una línea de la solicitud como referencia.
BLOQUES_POR_LINEA = (BLOQUE_RESULTADOS, BLOQUE_FOTOS)
# Bloques que quien tiene PERMISO_EDITAR_DATOS puede convertir en texto
# editable. Fotos y firmas nunca: las imágenes y la firma salen del sistema.
BLOQUES_CONVERTIBLES = (BLOQUE_CARATULA, BLOQUE_RESULTADOS, BLOQUE_EQUIPOS, BLOQUE_NOTAS)
PERMISO_EDITAR_DATOS = 'informes.editar_datos'

ETIQUETAS_EQUIPO = {'prensa': 'Prensa', 'balanza': 'Balanza', 'vernier': 'Vernier',
                    'termohigrometro': 'Termohigrómetro', 'cuna': 'Cuña', 'escuadra': 'Escuadra'}

MODO_WEB = 'web'
MODO_PDF = 'pdf'


def clave_bloque(tipo, ref=''):
    return f"{tipo}:{ref}" if ref else tipo


def _bloque(tipo, ref=''):
    return {'type': 'bloqueDatos', 'attrs': {'tipo': tipo, 'ref': str(ref) if ref else ''}}


def _titulo(nivel, texto):
    return {'type': 'heading', 'attrs': {'level': nivel}, 'content': [{'type': 'text', 'text': texto}]}


def _parrafo(texto=''):
    nodo = {'type': 'paragraph'}
    if texto:
        nodo['content'] = [{'type': 'text', 'text': texto}]
    return nodo


def _hay_sesiones(lineas):
    return any(getattr(d, 'resultado', None) and d.resultado.sesion_id for d in lineas)


def documento_inicial(solicitud):
    """Borrador con la estructura del modelo de informe del laboratorio."""
    lineas = list(lineas_resultados(solicitud))
    contenido = [
        _titulo(1, 'Informe de ensayo'),
        _bloque(BLOQUE_CARATULA),
        _titulo(2, 'Resultados'),
    ]
    for d in lineas:
        contenido.append(_titulo(3, f"{d.muestra.codigo_laboratorio} · {d.descripcion_ensayo or d.norma}"))
        contenido.append(_bloque(BLOQUE_RESULTADOS, d.pk))
        contenido.append(_bloque(BLOQUE_FOTOS, d.pk))
    contenido += [
        _titulo(2, 'Observaciones'),
        _parrafo(),
        _titulo(2, 'Conclusiones'),
        _parrafo(),
        _bloque(BLOQUE_NOTAS),
        _bloque(BLOQUE_FIRMAS),
    ]
    return {'type': 'doc', 'content': contenido}


def bloques_disponibles(solicitud, lineas=None):
    """Bloques que se pueden insertar desde el menú, en orden."""
    lineas = list(lineas_resultados(solicitud)) if lineas is None else lineas
    lista = [{'tipo': BLOQUE_CARATULA, 'ref': '', 'titulo': TIPOS_BLOQUE[BLOQUE_CARATULA]}]
    for d in lineas:
        for tipo in BLOQUES_POR_LINEA:
            lista.append({
                'tipo': tipo, 'ref': str(d.pk),
                'titulo': f"{TIPOS_BLOQUE[tipo]} · {d.muestra.codigo_laboratorio}",
            })
    if _hay_sesiones(lineas):
        lista.append({'tipo': BLOQUE_EQUIPOS, 'ref': '', 'titulo': TIPOS_BLOQUE[BLOQUE_EQUIPOS]})
    lista.append({'tipo': BLOQUE_NOTAS, 'ref': '', 'titulo': TIPOS_BLOQUE[BLOQUE_NOTAS]})
    lista.append({'tipo': BLOQUE_FIRMAS, 'ref': '', 'titulo': TIPOS_BLOQUE[BLOQUE_FIRMAS]})
    return lista


def bloques_editados(doc):
    """{clave: contenido} de los bloques que se convirtieron en texto editable."""
    editados = {}

    def recorrer(nodo):
        if nodo.get('type') == 'bloqueEditado':
            attrs = nodo.get('attrs') or {}
            editados[clave_bloque(attrs.get('tipo', ''), attrs.get('ref', ''))] = nodo.get('content') or []
            return
        for hijo in nodo.get('content') or []:
            recorrer(hijo)

    recorrer(doc or {})
    return editados


def bloques_usados(doc):
    """Claves de los bloques de datos que hay en el documento (también los
    convertidos en texto editable, que cuentan como presentes)."""
    claves = []

    def recorrer(nodo):
        if nodo.get('type') in ('bloqueDatos', 'bloqueEditado'):
            attrs = nodo.get('attrs') or {}
            claves.append(clave_bloque(attrs.get('tipo', ''), attrs.get('ref', '')))
        for hijo in nodo.get('content') or []:
            recorrer(hijo)

    recorrer(doc)
    return claves


def bloques_faltantes(doc, solicitud, lineas=None):
    """Bloques obligatorios que no están: carátula, resultados de cada línea y firmas."""
    lineas = list(lineas_resultados(solicitud)) if lineas is None else lineas
    usados = set(bloques_usados(doc))
    faltan = []
    if BLOQUE_CARATULA not in usados:
        faltan.append(TIPOS_BLOQUE[BLOQUE_CARATULA])
    for d in lineas:
        if clave_bloque(BLOQUE_RESULTADOS, d.pk) not in usados:
            faltan.append(f"Resultados de {d.muestra.codigo_laboratorio}")
    if BLOQUE_FIRMAS not in usados:
        faltan.append(TIPOS_BLOQUE[BLOQUE_FIRMAS])
    return faltan


# --- Validación del JSON que llega del navegador ------------------------------

class DocumentoInvalido(ValueError):
    pass


NODOS_PERMITIDOS = {
    'doc', 'paragraph', 'heading', 'text', 'bulletList', 'orderedList', 'listItem',
    'table', 'tableRow', 'tableHeader', 'tableCell', 'hardBreak', 'horizontalRule', 'bloqueDatos',
    'bloqueEditado',
}
MARCAS_PERMITIDAS = {'bold', 'italic', 'underline', 'strike'}
ALINEACIONES = {'left', 'center', 'right', 'justify'}
MAX_NODOS = 20000
MAX_PROFUNDIDAD = 40
MAX_TEXTO = 20000


def _entero(valor, minimo, maximo, defecto):
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return defecto
    return min(max(valor, minimo), maximo)


def validar_contenido(doc):
    """Devuelve una copia limpia del documento o lanza DocumentoInvalido.

    Solo pasan los nodos, marcas y atributos que el renderizador conoce; el
    resto se descarta. Así el HTML del PDF nunca lleva nada que no hayamos
    escrito nosotros.
    """
    if not isinstance(doc, dict) or doc.get('type') != 'doc':
        raise DocumentoInvalido("El documento no tiene el formato del editor.")
    contador = [0]

    def limpiar(nodo, profundidad):
        if not isinstance(nodo, dict):
            return None
        tipo = nodo.get('type')
        if tipo not in NODOS_PERMITIDOS:
            return None
        contador[0] += 1
        if contador[0] > MAX_NODOS or profundidad > MAX_PROFUNDIDAD:
            raise DocumentoInvalido("El documento es demasiado grande.")
        limpio = {'type': tipo}
        attrs = nodo.get('attrs') if isinstance(nodo.get('attrs'), dict) else {}
        if tipo == 'text':
            texto = nodo.get('text')
            if not isinstance(texto, str) or not texto:
                return None
            limpio['text'] = texto[:MAX_TEXTO]
            marcas = [
                {'type': m['type']} for m in (nodo.get('marks') or [])
                if isinstance(m, dict) and m.get('type') in MARCAS_PERMITIDAS
            ]
            if marcas:
                limpio['marks'] = marcas
            return limpio
        if tipo == 'heading':
            limpio['attrs'] = {'level': _entero(attrs.get('level'), 1, 3, 2)}
        if tipo in ('paragraph', 'heading') and attrs.get('textAlign') in ALINEACIONES:
            limpio.setdefault('attrs', {})['textAlign'] = attrs['textAlign']
        if tipo == 'orderedList':
            limpio['attrs'] = {'start': _entero(attrs.get('start'), 1, 9999, 1)}
        if tipo in ('tableCell', 'tableHeader'):
            limpio['attrs'] = {
                'colspan': _entero(attrs.get('colspan'), 1, 20, 1),
                'rowspan': _entero(attrs.get('rowspan'), 1, 50, 1),
            }
        if tipo == 'bloqueDatos':
            bloque = attrs.get('tipo')
            if bloque not in TIPOS_BLOQUE:
                return None
            ref = str(attrs.get('ref') or '')
            if bloque in BLOQUES_POR_LINEA and not ref.isdigit():
                return None
            limpio['attrs'] = {'tipo': bloque, 'ref': ref if bloque in BLOQUES_POR_LINEA else ''}
            return limpio
        if tipo == 'bloqueEditado':
            bloque = attrs.get('tipo')
            ref = str(attrs.get('ref') or '')
            if bloque not in BLOQUES_CONVERTIBLES or profundidad != 1:
                return None
            if bloque in BLOQUES_POR_LINEA and not ref.isdigit():
                return None
            limpio['attrs'] = {'tipo': bloque, 'ref': ref if bloque in BLOQUES_POR_LINEA else ''}
        hijos = []
        for hijo in nodo.get('content') or []:
            h = limpiar(hijo, profundidad + 1)
            if h is not None:
                hijos.append(h)
        if hijos:
            limpio['content'] = hijos
        elif tipo == 'bloqueEditado':
            return None
        return limpio

    return limpiar(doc, 0)


# --- Datos de los bloques -----------------------------------------------------

def datos_informe(solicitud, modo=MODO_WEB, informe=None, firmante=None, lineas=None):
    """Lo que dibujan los bloques, leído siempre de la base."""
    cotizacion = solicitud.cotizacion
    cliente = cotizacion.cliente
    recepcion = solicitud.recepcion
    proyecto = Proyecto.objects.filter(cotizacion=cotizacion).only('nombre_proyecto').first()
    lineas = list(lineas_resultados(solicitud)) if lineas is None else lineas

    por_linea = {}
    sesiones = {}
    fechas = set()
    for d in lineas:
        e = getattr(d, 'resultado', None)
        fotos = []
        if e is not None:
            orden = {c: i for i, (c, _) in enumerate(FotoEnsayo.tipos_de(e.plantilla))}
            for f in sorted(e.fotos.all(), key=lambda f: orden.get(f.tipo, 99)):
                src = _uri(f.imagen) if modo == MODO_PDF else reverse('proyectos:foto_compresion', args=[f.pk])
                fotos.append({'src': src, 'etiqueta': f.get_tipo_display(), 'ancho': f.ancho, 'alto': f.alto})
            if e.fecha_ensayo:
                fechas.add(e.fecha_ensayo)
            if e.sesion_id:
                sesiones[e.sesion_id] = e.sesion
        sesion = e.sesion if e is not None and e.sesion_id else None
        por_linea[str(d.pk)] = {
            'detalle': d,
            'muestra': d.muestra,
            'ensayo': e,
            'es_compresion': bool(e and e.plantilla == ResultadoEnsayo.PLANTILLA_COMPRESION),
            'fotos': fotos,
            'sesion': sesion,
            'equipos': sesion.equipos_usados() if sesion else [],
            'fractura': dict(FRACTURAS).get(e.tipo_fractura) if e is not None and e.tipo_fractura else '',
        }

    etiquetas = ETIQUETAS_EQUIPO
    metodos = {}
    for d in lineas:
        clave = (d.descripcion_ensayo or d.norma, d.norma)
        metodos[clave] = metodos.get(clave, 0) + 1
    negocio = _negocio()
    direccion = (
        f"{negocio.direccion_calle} - {negocio.direccion_localidad}" if negocio else "Jr. Los Topacios 440 - Cajamarca"
    )
    equipos = []
    for s in sorted(sesiones.values(), key=lambda s: (s.fecha, s.pk)):
        equipos.append({
            'sesion': s,
            'tecnico': s.tecnico.nombre_completo if s.tecnico_id else '',
            'equipos': s.equipos_usados(),
            'comprobacion': s.comprobacion_items(),
        })

    firma = None
    if firmante is not None:
        firma = {
            'nombre': firmante.get_nombre_formal(),
            'cargo': firmante.rol.nombre if firmante.rol_id else 'Jefe de Laboratorio',
            'imagen': (
                (_uri(firmante.firma_electronica) if modo == MODO_PDF else '')
                if firmante.firma_electronica else ''
            ),
        }
    return {
        'solicitud': solicitud,
        'informe': informe,
        'cliente': {
            'razon_social': cliente.razon_social,
            'ruc': cliente.ruc,
            'direccion': cliente.direccion or '-',
            'contacto': cotizacion.persona_contacto or cliente.persona_contacto or '-',
            'correo': cotizacion.correo_contacto or cliente.correo_contacto or '-',
        },
        'proyecto': (proyecto.nombre_proyecto if proyecto else '') or cotizacion.proyecto_asociado or '-',
        'ubicacion': getattr(recepcion, 'ubicacion_informe', '') or '-',
        'recepcion': timezone.localtime(recepcion.fecha_recepcion).date() if recepcion.fecha_recepcion else None,
        'fechas_ensayo': sorted(fechas),
        'lineas': por_linea,
        'equipos': equipos,
        'firma': firma,
        'metodos': [{'nombre': n, 'norma': norma, 'cantidad': c} for (n, norma), c in metodos.items()],
        'hay_compresion': any(v['es_compresion'] for v in por_linea.values()),
        'notas_items': NOTAS_ITEMS,
        'notas': [n.format(direccion=direccion) for n in NOTAS],
        'anexos': ANEXOS,
        'qr': '',
        'modo': modo,
    }


def render_bloque(tipo, ref, datos):
    contexto = {'datos': datos, 'tipo': tipo, 'titulo': TIPOS_BLOQUE.get(tipo, '')}
    if tipo in BLOQUES_POR_LINEA:
        linea = datos['lineas'].get(str(ref))
        if linea is None:
            return '<div class="bloque bloque--vacio">Esta línea ya no pertenece a la solicitud.</div>'
        contexto['linea'] = linea
    return render_to_string(f'proyectos/informe_bloques/{tipo}.html', contexto)


def html_de_bloques(solicitud, datos=None):
    """{clave: html} de todos los bloques disponibles (para el editor)."""
    lineas = list(lineas_resultados(solicitud))
    datos = datos or datos_informe(solicitud, MODO_WEB, lineas=lineas)
    return {
        clave_bloque(b['tipo'], b['ref']): render_bloque(b['tipo'], b['ref'], datos)
        for b in bloques_disponibles(solicitud, lineas)
    }


# --- JSON → HTML ----------------------------------------------------------------

ETIQUETAS_MARCA = {'bold': 'strong', 'italic': 'em', 'underline': 'u', 'strike': 's'}


def render_documento(doc, datos):
    """HTML del documento ya validado. Todo texto se escapa."""
    partes = []

    def estilo(attrs):
        alineacion = (attrs or {}).get('textAlign')
        return f' style="text-align:{alineacion}"' if alineacion in ALINEACIONES else ''

    def hijos(nodo):
        for h in nodo.get('content') or []:
            dibujar(h)

    def dibujar(nodo):
        tipo = nodo.get('type')
        attrs = nodo.get('attrs') or {}
        if tipo == 'text':
            texto = escape(nodo.get('text', ''))
            for m in nodo.get('marks') or []:
                etiqueta = ETIQUETAS_MARCA.get(m.get('type'))
                if etiqueta:
                    texto = f'<{etiqueta}>{texto}</{etiqueta}>'
            partes.append(texto)
        elif tipo == 'doc':
            hijos(nodo)
        elif tipo == 'paragraph':
            partes.append(f'<p{estilo(attrs)}>')
            hijos(nodo)
            partes.append('</p>')
        elif tipo == 'heading':
            nivel = _entero(attrs.get('level'), 1, 3, 2)
            partes.append(f'<h{nivel}{estilo(attrs)}>')
            hijos(nodo)
            partes.append(f'</h{nivel}>')
        elif tipo == 'bulletList':
            partes.append('<ul>')
            hijos(nodo)
            partes.append('</ul>')
        elif tipo == 'orderedList':
            inicio = _entero(attrs.get('start'), 1, 9999, 1)
            partes.append(f'<ol start="{inicio}">' if inicio != 1 else '<ol>')
            hijos(nodo)
            partes.append('</ol>')
        elif tipo == 'listItem':
            partes.append('<li>')
            hijos(nodo)
            partes.append('</li>')
        elif tipo == 'table':
            partes.append('<table class="tabla-libre"><tbody>')
            hijos(nodo)
            partes.append('</tbody></table>')
        elif tipo == 'tableRow':
            partes.append('<tr>')
            hijos(nodo)
            partes.append('</tr>')
        elif tipo in ('tableCell', 'tableHeader'):
            etiqueta = 'th' if tipo == 'tableHeader' else 'td'
            colspan = _entero(attrs.get('colspan'), 1, 20, 1)
            rowspan = _entero(attrs.get('rowspan'), 1, 50, 1)
            extra = (f' colspan="{colspan}"' if colspan > 1 else '') + (f' rowspan="{rowspan}"' if rowspan > 1 else '')
            partes.append(f'<{etiqueta}{extra}>')
            hijos(nodo)
            partes.append(f'</{etiqueta}>')
        elif tipo == 'hardBreak':
            partes.append('<br>')
        elif tipo == 'horizontalRule':
            partes.append('<hr>')
        elif tipo == 'bloqueDatos':
            partes.append(render_bloque(attrs.get('tipo'), attrs.get('ref', ''), datos))
        elif tipo == 'bloqueEditado':
            partes.append('<div class="bloque bloque-editado">')
            hijos(nodo)
            partes.append('</div>')

    dibujar(doc)
    return ''.join(partes)


def html_informe(borrador, modo=MODO_WEB, informe=None, firmante=None):
    """Página completa del informe (vista previa o PDF)."""
    solicitud = borrador.solicitud
    datos = datos_informe(solicitud, modo, informe=informe, firmante=firmante)
    if modo == MODO_PDF:
        logo = (Path(settings.BASE_DIR) / 'static' / 'img' / 'LogoF.png').as_uri()
        datos['qr'] = _uri(informe.qr_code) if informe and informe.qr_code else ''
    else:
        logo = settings.STATIC_URL + 'img/LogoF.png'
    cuerpo = render_documento(validar_contenido(borrador.contenido), datos)
    return render_to_string('proyectos/informe_editor_pdf.html', {
        'cuerpo': cuerpo,
        'datos': datos,
        'informe': informe,
        'negocio': _negocio(),
        'logo': logo,
        'modo': modo,
    })


def generar_pdf_borrador(html):
    from weasyprint import HTML
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
