"""Sanitizado del HTML de los correos (recibidos y redactados).

Todo HTML que entra a la base pasa por `sanitizar_html` (nh3, en Rust): sin
scripts, sin manejadores on*, sin javascript:, con estilos filtrados. Además
se muestra en un iframe sandbox sin scripts y con su propia CSP
(views_correo.mensaje_cuerpo). Las imágenes remotas se bloquean al mostrar,
no al guardar, para poder activarlas con "Mostrar imágenes".
"""
import html as html_lib
import re
import unicodedata

import nh3

ETIQUETAS = set(nh3.ALLOWED_TAGS) | {'font', 'u', 's', 'center'}
ATRIBUTOS = {
    '*': {'style', 'align', 'valign', 'width', 'height', 'bgcolor', 'dir', 'title',
          'colspan', 'rowspan', 'border', 'cellpadding', 'cellspacing', 'lang'},
    'a': {'href', 'title', 'name'},
    'img': {'src', 'alt', 'width', 'height', 'title'},
    'font': {'color', 'face', 'size'},
    'ol': {'start', 'type'},
    'li': {'value'},
    'blockquote': {'type', 'cite'},
}
PROPIEDADES_CSS = {
    'color', 'background-color', 'font', 'font-size', 'font-family', 'font-weight', 'font-style',
    'text-decoration', 'text-align', 'text-indent', 'line-height', 'letter-spacing', 'white-space',
    'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'border', 'border-top', 'border-right', 'border-bottom', 'border-left', 'border-color',
    'border-width', 'border-style', 'border-collapse', 'border-radius',
    'width', 'height', 'max-width', 'min-width', 'vertical-align', 'list-style-type',
}
ESQUEMAS = {'http', 'https', 'mailto', 'tel', 'cid', 'data'}


def _filtro_atributos(etiqueta, atributo, valor):
    """data: solo como imagen raster en <img src> (firmas, imágenes pegadas)."""
    if valor.lower().startswith('data:'):
        es_imagen = valor.lower().startswith(('data:image/png', 'data:image/jpeg', 'data:image/gif', 'data:image/webp'))
        return valor if (etiqueta == 'img' and atributo == 'src' and es_imagen) else None
    return valor


def sanitizar_html(contenido):
    if not contenido:
        return ''
    return nh3.clean(
        contenido,
        tags=ETIQUETAS,
        clean_content_tags={'script', 'style', 'title', 'head'},
        attributes=ATRIBUTOS,
        url_schemes=ESQUEMAS,
        attribute_filter=_filtro_atributos,
        filter_style_properties=PROPIEDADES_CSS,
        link_rel='noopener noreferrer',
        set_tag_attribute_values={'a': {'target': '_blank'}},
        strip_comments=True,
    )


_IMG_REMOTA = re.compile(r'(<img\b[^>]*?\s)src="(https?://[^"]*)"', re.IGNORECASE)


def bloquear_imagenes_remotas(contenido):
    """Cambia src remoto por data-src-bloqueada. Devuelve (html, cuántas)."""
    cuenta = 0

    def _cambiar(m):
        nonlocal cuenta
        cuenta += 1
        return f'{m.group(1)}data-src-bloqueada="{m.group(2)}" title="Imagen remota bloqueada"'

    return _IMG_REMOTA.sub(_cambiar, contenido or ''), cuenta


def tiene_imagenes_remotas(contenido):
    return bool(_IMG_REMOTA.search(contenido or ''))


_CID = re.compile(r'src="cid:([^"]+)"', re.IGNORECASE)


def reemplazar_cid(contenido, url_de_cid):
    """src="cid:X" -> src="<url firmada>" con la función dada (None = se deja)."""
    def _cambiar(m):
        url = url_de_cid(m.group(1))
        return f'src="{html_lib.escape(url)}"' if url else m.group(0)
    return _CID.sub(_cambiar, contenido or '')


def html_a_texto(contenido):
    sin_bloques = re.sub(r'(?i)<\s*(br|/p|/div|/tr|/li|/h\d)\s*/?>', '\n', contenido or '')
    texto = html_lib.unescape(nh3.clean(sin_bloques, tags=set()))
    return re.sub(r'\n{3,}', '\n\n', texto).strip()


def texto_a_html(texto):
    parrafos = [p for p in re.split(r'\n{2,}', texto or '') if p.strip()]
    return ''.join(f'<p>{html_lib.escape(p).replace(chr(10), "<br>")}</p>' for p in parrafos)


def vista_previa(texto, largo=180):
    plano = re.sub(r'\s+', ' ', texto or '').strip()
    return plano if len(plano) <= largo else plano[: largo - 1].rstrip() + '…'


def sin_tildes(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto or '') if unicodedata.category(c) != 'Mn'
    )
