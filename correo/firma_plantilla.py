"""Firma con plantilla: el usuario llena datos (nombre, cargo, teléfono…), sube su
logo y ajusta tamaño, posición y colores; el servidor arma el HTML.

Es HTML de correo: tablas y estilos en línea. Gmail y Outlook no muestran
imágenes en base64 ni SVG, así que el logo y los íconos son URL https públicas
del sitio (PNG). Todo valor del usuario se escapa, las redes solo aceptan
https:// y los colores solo #RRGGBB.
"""
import html as html_lib
import io
import re

from django.conf import settings
from django.templatetags.static import static

AZUL = '#12306B'
NARANJA = '#F5A623'
FONDO = '#F3F6FC'
GRIS = '#334155'
FUENTE = 'font-family:Arial,Helvetica,sans-serif'

CAMPOS_TEXTO = (
    ('nombre', 'Nombre', 80),
    ('cargo', 'Cargo', 80),
    ('telefono', 'Teléfono', 40),
    ('correo', 'Correo', 120),
    ('direccion', 'Dirección', 120),
    ('ciudad', 'Ciudad', 80),
)
CAMPOS_REDES = (
    ('web', 'Página web', 'Web'),
    ('facebook', 'Facebook', 'Facebook'),
    ('instagram', 'Instagram', 'Instagram'),
    ('tiktok', 'TikTok', 'TikTok'),
)
POSICIONES = (('izquierda', 'Logo a la izquierda'), ('arriba', 'Logo arriba'))
LOGO_ANCHO_MIN, LOGO_ANCHO_MAX, LOGO_ANCHO_INICIAL = 50, 260, 90
LOGO_MAX_BYTES = 2 * 1024 * 1024
OPCIONES_INICIALES = {
    'logo_ancho': LOGO_ANCHO_INICIAL, 'logo_pos': 'izquierda',
    'color_principal': AZUL, 'color_acento': NARANJA, 'color_panel': FONDO,
}
_HTTPS = re.compile(r'^https://[^\s"<>]+$', re.IGNORECASE)
_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')


def _url_estatica(ruta, base=None):
    url = static(ruta)
    if url.startswith('http'):
        return url
    return (base or settings.SITE_URL).rstrip('/') + url


def url_logo(base=None):
    return _url_estatica('img/LogoF.png', base)


def url_icono(nombre, base=None):
    """PNG (círculo naranja con el símbolo en azul) alojado en el sitio."""
    return _url_estatica(f'img/firma/{nombre}.png', base)


def url_publica(ruta_media):
    """URL absoluta (para el destinatario) de un archivo subido a MEDIA."""
    return settings.SITE_URL.rstrip('/') + ruta_media


def datos_iniciales(usuario=None):
    """Valores sugeridos desde la configuración del negocio (NAP en un solo lugar)."""
    from siteconfig.models import NegocioConfig
    n = NegocioConfig.objects.first()
    nombre = (usuario.get_full_name() or '').strip() if usuario is not None else ''
    datos = {'nombre': nombre, 'cargo': '', 'telefono': '', 'correo': getattr(usuario, 'email', '') or '',
             'direccion': '', 'ciudad': '', 'web': '', 'facebook': '', 'instagram': '', 'tiktok': '',
             **OPCIONES_INICIALES}
    if n:
        datos.update(telefono=n.telefono, direccion=n.direccion_calle, ciudad=n.direccion_localidad,
                     web=settings.SITE_URL if settings.SITE_URL.startswith('https://') else '',
                     facebook=n.facebook_url, instagram=n.instagram_url)
        if not datos['correo']:
            datos['correo'] = n.correo
    return datos


def limpiar_datos(origen):
    """Recorta, quita saltos de línea, descarta redes que no sean https:// y
    deja las opciones de diseño dentro de rango."""
    datos = {}
    for clave, _etiqueta, largo in CAMPOS_TEXTO:
        datos[clave] = re.sub(r'\s+', ' ', (origen.get(clave) or '')).strip()[:largo]
    for clave, _etiqueta, _marca in CAMPOS_REDES:
        valor = (origen.get(clave) or '').strip()[:200]
        datos[clave] = valor if _HTTPS.match(valor) else ''
    try:
        ancho = int(origen.get('logo_ancho') or LOGO_ANCHO_INICIAL)
    except (TypeError, ValueError):
        ancho = LOGO_ANCHO_INICIAL
    datos['logo_ancho'] = max(LOGO_ANCHO_MIN, min(LOGO_ANCHO_MAX, ancho))
    datos['logo_pos'] = origen.get('logo_pos') if origen.get('logo_pos') in dict(POSICIONES) else 'izquierda'
    for clave in ('color_principal', 'color_acento', 'color_panel'):
        valor = (origen.get(clave) or '').strip()
        datos[clave] = valor.upper() if _COLOR.match(valor) else OPCIONES_INICIALES[clave]
    return datos


def errores_de(datos, origen=None):
    errores = []
    if not datos['nombre']:
        errores.append('Escribe el nombre que va en la firma.')
    if origen is not None:
        for clave, etiqueta, _m in CAMPOS_REDES:
            crudo = (origen.get(clave) or '').strip()
            if crudo and not datos[clave]:
                errores.append(f'{etiqueta}: el enlace debe empezar con https://')
    return errores


def procesar_logo(archivo):
    """Valida y normaliza el logo subido. Devuelve (extensión, bytes).

    Acepta PNG, JPG y WEBP de hasta 2 MB; lo reduce a 600 px de lado y lo
    vuelve a guardar (así se pierden metadatos y cualquier contenido extra).
    Lanza ValueError con un texto para mostrar al usuario."""
    from PIL import Image
    if archivo.size > LOGO_MAX_BYTES:
        raise ValueError('El logo pesa más de 2 MB.')
    try:
        img = Image.open(archivo)
        formato = img.format
        if formato not in ('PNG', 'JPEG', 'WEBP'):
            raise ValueError('El logo debe ser PNG, JPG o WEBP.')
        if img.width * img.height > 25_000_000:
            raise ValueError('La imagen es demasiado grande.')
        img.load()
    except ValueError:
        raise
    except Exception:  # noqa: BLE001 - cualquier fallo de Pillow = archivo no válido
        raise ValueError('El archivo no es una imagen válida (PNG, JPG o WEBP).')
    img.thumbnail((600, 600))
    salida = io.BytesIO()
    if img.mode in ('RGBA', 'LA', 'P'):
        img.convert('RGBA').save(salida, 'PNG', optimize=True)
        return 'png', salida.getvalue()
    img.convert('RGB').save(salida, 'JPEG', quality=88, optimize=True)
    return 'jpg', salida.getvalue()


def _e(texto):
    return html_lib.escape(texto, quote=True)


def _fila(icono, texto, enlace, base):
    if not texto:
        return ''
    contenido = _e(texto)
    if enlace:
        contenido = f'<a href="{_e(enlace)}" style="color:{GRIS};text-decoration:none">{contenido}</a>'
    return (
        f'<tr>'
        f'<td width="24" valign="middle" style="width:24px;padding:1px 8px 1px 0">'
        f'<img src="{_e(url_icono(icono, base))}" alt="" width="16" height="16" style="width:16px;height:16px"></td>'
        f'<td valign="middle" style="padding:1px 0;{FUENTE};font-size:12px;line-height:16px;color:{GRIS}">{contenido}</td>'
        f'</tr>')


def _boton(enlace, icono, etiqueta, base):
    return (
        f'<td valign="middle" style="padding:0 6px 0 0"><a href="{_e(enlace)}" title="{_e(etiqueta)}">'
        f'<img src="{_e(url_icono(icono, base))}" alt="{_e(etiqueta)}" width="22" height="22" '
        f'style="width:22px;height:22px;border-radius:11px"></a></td>')


def generar_html(datos, logo_url=None, base=None):
    """HTML de la firma (listo para pasar por sanitizar_html).

    logo_url: URL del logo subido (None = el de Grupo VICAF). base: origen que
    reemplaza a SITE_URL en los íconos; solo para la vista previa."""
    d = {**OPCIONES_INICIALES, **datos}
    principal, acento, panel = d['color_principal'], d['color_acento'], d['color_panel']
    ancho = d['logo_ancho']
    ubicacion = ', '.join(p for p in (d['direccion'], d['ciudad']) if p)
    telefono_enlace = f"tel:{re.sub(r'[^0-9+]', '', d['telefono'])}" if re.search(r'\d', d['telefono']) else None
    filas = ''.join((
        _fila('telefono', d['telefono'], telefono_enlace, base),
        _fila('correo', d['correo'], f"mailto:{d['correo']}" if '@' in d['correo'] else None, base),
        _fila('sede', ubicacion, None, base),
    ))
    cargo = (f'<div style="{FUENTE};font-size:10px;line-height:14px;font-weight:bold;letter-spacing:1px;'
             f'color:{acento};padding:1px 0 6px 0">{_e(d["cargo"].upper())}</div>') if d['cargo'] else (
        '<div style="height:5px;line-height:5px">&nbsp;</div>')
    botones = ''.join(_boton(d[c], c, etiqueta, base) for c, etiqueta, _m in CAMPOS_REDES if d[c])
    barra_redes = (
        f'<tr><td colspan="2" bgcolor="{principal}" style="background-color:{principal};padding:6px 12px">'
        f'<table cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td valign="middle" style="padding:0 14px 0 0;{FUENTE};font-size:10px;font-weight:bold;'
        f'letter-spacing:1px;color:#ffffff">SÍGUENOS</td>{botones}</tr></table></td></tr>'
    ) if botones else ''
    imagen = (f'<img src="{_e(logo_url or url_logo(base))}" alt="Logo" width="{ancho}" '
              f'style="width:{ancho}px;height:auto">')
    informacion = (
        f'<div style="{FUENTE};font-size:15px;line-height:20px;font-weight:bold;color:{principal}">{_e(d["nombre"])}</div>'
        f'{cargo}'
        f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">{filas}</table>')
    if d['logo_pos'] == 'arriba':
        cuerpo = (
            f'<tr><td colspan="2" align="left" bgcolor="{panel}" style="padding:10px 14px;background-color:{panel}">'
            f'{imagen}</td></tr>'
            f'<tr><td colspan="2" valign="middle" style="padding:10px 14px;border-bottom:1px solid #E2E8F0">'
            f'{informacion}</td></tr>')
    else:
        cuerpo = (
            f'<tr><td width="{ancho + 28}" valign="middle" align="center" bgcolor="{panel}" '
            f'style="width:{ancho + 28}px;padding:10px 14px;background-color:{panel}">{imagen}</td>'
            f'<td valign="middle" style="padding:10px 14px;border-bottom:1px solid #E2E8F0">{informacion}</td></tr>')
    return (
        f'<table cellpadding="0" cellspacing="0" border="0" width="440" '
        f'style="width:440px;max-width:100%;border-collapse:collapse;margin-top:10px">'
        f'<tr><td width="40%" height="4" bgcolor="{principal}" style="height:4px;line-height:4px;font-size:1px;'
        f'background-color:{principal}">&nbsp;</td>'
        f'<td height="4" bgcolor="{acento}" style="height:4px;line-height:4px;font-size:1px;'
        f'background-color:{acento}">&nbsp;</td></tr>'
        f'{cuerpo}'
        f'{barra_redes}'
        f'</table>'
    )
