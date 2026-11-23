"""La firma con plantilla va en el borrador como un bloque aparte del texto.

El editor del correo (Quill) no soporta tablas con estilos y las desarma, así
que ese HTML nunca pasa por él: el borrador guarda
    <texto del editor><div data-vicaf-firma="1">…firma…</div>
y la pantalla de redactar muestra el bloque en un marco aparte, con su propio
botón «Quitar firma». Al guardar, el servidor conserva el bloque que ya tenía.
"""
import base64
import re

from django.conf import settings
from django.core.files.storage import default_storage

APERTURA = '<div data-vicaf-firma="1">'
_CIERRE = '</div>'


def envolver(html):
    return f'{APERTURA}{html}{_CIERRE}' if html else ''


def separar(html):
    """(texto del editor, firma) a partir del HTML guardado; firma '' si no hay."""
    html = html or ''
    i = html.rfind(APERTURA)
    resto = html[i:].rstrip() if i != -1 else ''
    if i == -1 or not resto.endswith(_CIERRE):
        return html, ''
    return html[:i], resto[len(APERTURA):-len(_CIERRE)]


_TABLA = re.compile(r'<table\b.*?</table>', re.IGNORECASE | re.DOTALL)


def quitar_firma_vieja(html):
    """(html sin la tabla de firma, hubo). Los borradores hechos antes del bloque
    fijo guardaron la firma como tabla dentro del texto (ya desarmada por el
    editor); se reconoce por los íconos de la firma (static/img/firma/)."""
    hubo = False

    def _quitar(m):
        nonlocal hubo
        if '/img/firma/' in m.group(0):
            hubo = True
            return ''
        return m.group(0)

    return _TABLA.sub(_quitar, html or ''), hubo


def para_vista(html, origen):
    """Firma guardada -> HTML que se ve igual en local y en producción.

    Los íconos y el logo se guardan con la URL pública (SITE_URL). Para la
    vista previa los íconos se sirven desde `origen` (este mismo host) y los
    logos subidos se incrustan como data:, sin depender de qué host sirve MEDIA."""
    base = settings.SITE_URL.rstrip('/')
    html = html.replace(f'{base}/static/', f'{origen}/static/')

    def _incrustar(m):
        ruta = m.group(1)
        try:
            with default_storage.open(ruta, 'rb') as f:
                contenido = f.read()
        except (OSError, ValueError):
            return m.group(0)
        tipo = 'image/png' if ruta.lower().endswith('.png') else 'image/jpeg'
        return f'src="data:{tipo};base64,{base64.b64encode(contenido).decode()}"'

    return re.sub(rf'src="{re.escape(base)}/media/([^"]+)"', _incrustar, html)
