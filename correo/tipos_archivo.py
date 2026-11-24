"""Tipo de archivo de un adjunto (PDF, Excel, Word…) para mostrarlo con su etiqueta de color.

La clave se usa como clase CSS (`tipo--pdf`) y la etiqueta es el texto corto del icono.
static/correo/js/redactar.js repite esta tabla por extensión para la lista de Redactar.
"""
import os

POR_EXTENSION = {
    'pdf': ('pdf', 'PDF'),
    **dict.fromkeys(('xls', 'xlsx', 'xlsm', 'xlsb', 'csv', 'ods'), ('excel', 'XLS')),
    **dict.fromkeys(('doc', 'docx', 'docm', 'rtf', 'odt'), ('word', 'DOC')),
    **dict.fromkeys(('ppt', 'pptx', 'pps', 'ppsx', 'odp'), ('ppt', 'PPT')),
    **dict.fromkeys(('png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'heic', 'tif', 'tiff'), ('imagen', 'IMG')),
    **dict.fromkeys(('zip', 'rar', '7z', 'tar', 'gz'), ('zip', 'ZIP')),
    **dict.fromkeys(('txt', 'log', 'md'), ('texto', 'TXT')),
    **dict.fromkeys(('xml', 'json'), ('xml', 'XML')),
    **dict.fromkeys(('dwg', 'dxf'), ('cad', 'CAD')),
    **dict.fromkeys(('eml', 'msg'), ('correo', 'EML')),
}
POR_MIME = (
    ('application/pdf', ('pdf', 'PDF')),
    ('image/', ('imagen', 'IMG')),
    ('spreadsheet', ('excel', 'XLS')),
    ('ms-excel', ('excel', 'XLS')),
    ('wordprocessing', ('word', 'DOC')),
    ('msword', ('word', 'DOC')),
    ('presentation', ('ppt', 'PPT')),
    ('ms-powerpoint', ('ppt', 'PPT')),
    ('zip', ('zip', 'ZIP')),
    ('text/xml', ('xml', 'XML')),
    ('application/xml', ('xml', 'XML')),
    ('text/plain', ('texto', 'TXT')),
)


def tipo_de(nombre, mime=''):
    """(clave, etiqueta) según la extensión del nombre y, si no basta, el tipo MIME."""
    extension = os.path.splitext(nombre or '')[1].lstrip('.').lower()
    if extension in POR_EXTENSION:
        return POR_EXTENSION[extension]
    mime = (mime or '').lower()
    for fragmento, tipo in POR_MIME:
        if fragmento in mime:
            return tipo
    return 'otro', (extension.upper()[:4] if 1 <= len(extension) <= 4 else 'ARCH')


# Lo que se puede abrir en el navegador sin riesgo: nunca HTML ni SVG (podrían ejecutar código).
VISTA_PREVIA_MIME = ('application/pdf', 'text/plain', 'image/png', 'image/jpeg', 'image/gif', 'image/webp')
VISTA_PREVIA_EXT = {'pdf': 'application/pdf', 'txt': 'text/plain', 'log': 'text/plain', 'csv': 'text/plain',
                    'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif',
                    'webp': 'image/webp'}


def tipo_vista_previa(nombre, mime=''):
    """Tipo MIME con el que se puede mostrar el adjunto en el navegador, o None (solo descarga)."""
    extension = os.path.splitext(nombre or '')[1].lstrip('.').lower()
    if extension in VISTA_PREVIA_EXT:
        return VISTA_PREVIA_EXT[extension]
    return mime if mime in VISTA_PREVIA_MIME else None
