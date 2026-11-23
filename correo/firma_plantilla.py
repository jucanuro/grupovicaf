"""Firma con plantilla: el usuario llena datos (nombre, cargo, teléfono…) y el
servidor arma el HTML. Es HTML de correo: tablas y estilos en línea, sin
imágenes en base64 (Gmail y Outlook no las muestran): el logo es una URL
https pública del sitio. Todo valor del usuario se escapa y las redes solo
aceptan https://.
"""
import html as html_lib
import re

from django.conf import settings
from django.templatetags.static import static

AZUL = '#12306B'
NARANJA = '#F5A623'
AZUL_CLARO = '#5B8DD6'
FONDO = '#F3F6FC'
GRIS = '#334155'
TENUE = '#64748B'
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
_HTTPS = re.compile(r'^https://[^\s"<>]+$', re.IGNORECASE)


def url_logo():
    ruta = static('img/LogoF.png')
    return ruta if ruta.startswith('http') else settings.SITE_URL.rstrip('/') + ruta


def datos_iniciales(usuario=None):
    """Valores sugeridos desde la configuración del negocio (NAP en un solo lugar)."""
    from siteconfig.models import NegocioConfig
    n = NegocioConfig.objects.first()
    nombre = ''
    if usuario is not None:
        nombre = (usuario.get_full_name() or '').strip()
    datos = {'nombre': nombre, 'cargo': '', 'telefono': '', 'correo': getattr(usuario, 'email', '') or '',
             'direccion': '', 'ciudad': '', 'web': '', 'facebook': '', 'instagram': '', 'tiktok': ''}
    if n:
        datos.update(telefono=n.telefono, direccion=n.direccion_calle, ciudad=n.direccion_localidad,
                     web=settings.SITE_URL if settings.SITE_URL.startswith('https://') else '',
                     facebook=n.facebook_url, instagram=n.instagram_url)
        if not datos['correo']:
            datos['correo'] = n.correo
    return datos


def limpiar_datos(origen):
    """Recorta, quita saltos de línea y descarta redes que no sean https://."""
    datos = {}
    for clave, _etiqueta, largo in CAMPOS_TEXTO:
        datos[clave] = re.sub(r'\s+', ' ', (origen.get(clave) or '')).strip()[:largo]
    for clave, _etiqueta, _marca in CAMPOS_REDES:
        valor = (origen.get(clave) or '').strip()[:200]
        datos[clave] = valor if _HTTPS.match(valor) else ''
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


def _e(texto):
    return html_lib.escape(texto, quote=True)


def _fila(etiqueta, texto, enlace=None):
    if not texto:
        return ''
    contenido = _e(texto)
    if enlace:
        contenido = f'<a href="{_e(enlace)}" style="color:{GRIS};text-decoration:none">{contenido}</a>'
    return (
        f'<tr>'
        f'<td width="44" valign="top" style="width:44px;padding:3px 8px 3px 0;{FUENTE};font-size:10px;'
        f'line-height:18px;font-weight:bold;letter-spacing:1px;color:{AZUL_CLARO}">{etiqueta}</td>'
        f'<td valign="top" style="padding:3px 0;{FUENTE};font-size:13px;line-height:18px;color:{GRIS}">{contenido}</td>'
        f'</tr>')


def _boton(enlace, texto):
    """Botón redondeado: es una celda porque el tamaño y el fondo solo valen ahí
    (el sanitizador no admite display ni degradados)."""
    return (
        f'<td bgcolor="{NARANJA}" style="background-color:{NARANJA};border-radius:14px;padding:5px 14px">'
        f'<a href="{_e(enlace)}" style="color:{AZUL};text-decoration:none;{FUENTE};font-size:12px;'
        f'font-weight:bold">{_e(texto)}</a></td>'
        f'<td width="8" style="width:8px"></td>')


def generar_html(datos):
    """HTML de la firma (ya listo para pasar por sanitizar_html)."""
    d = datos
    ubicacion = ', '.join(p for p in (d['direccion'], d['ciudad']) if p)
    telefono_enlace = f"tel:{re.sub(r'[^0-9+]', '', d['telefono'])}" if re.search(r'\d', d['telefono']) else None
    filas = ''.join((
        _fila('TEL', d['telefono'], telefono_enlace),
        _fila('MAIL', d['correo'], f"mailto:{d['correo']}" if '@' in d['correo'] else None),
        _fila('SEDE', ubicacion),
    ))
    cargo = (f'<div style="{FUENTE};font-size:11px;line-height:16px;font-weight:bold;letter-spacing:2px;'
             f'color:{NARANJA};padding:2px 0 10px 0">{_e(d["cargo"].upper())}</div>') if d['cargo'] else (
        '<div style="height:8px;line-height:8px">&nbsp;</div>')
    botones = ''.join(_boton(d[c], etiqueta) for c, _e_, etiqueta in CAMPOS_REDES if d[c])
    barra_redes = (
        f'<tr><td colspan="2" bgcolor="{AZUL}" style="background-color:{AZUL};padding:10px 16px">'
        f'<table cellpadding="0" cellspacing="0" border="0"><tr>{botones}</tr></table></td></tr>'
    ) if botones else ''
    return (
        f'<table cellpadding="0" cellspacing="0" border="0" width="520" '
        f'style="width:520px;max-width:100%;border-collapse:collapse;margin-top:14px">'
        f'<tr><td width="40%" height="4" bgcolor="{AZUL}" style="height:4px;line-height:4px;font-size:1px;'
        f'background-color:{AZUL}">&nbsp;</td>'
        f'<td height="4" bgcolor="{NARANJA}" style="height:4px;line-height:4px;font-size:1px;'
        f'background-color:{NARANJA}">&nbsp;</td></tr>'
        f'<tr>'
        f'<td width="170" valign="middle" align="center" bgcolor="{FONDO}" style="width:170px;padding:16px 20px;background-color:{FONDO}">'
        f'<img src="{_e(url_logo())}" alt="Grupo VICAF" width="120" style="width:120px;height:auto">'
        f'</td>'
        f'<td valign="middle" style="padding:16px 20px;border-bottom:1px solid #E2E8F0">'
        f'<div style="{FUENTE};font-size:19px;line-height:24px;font-weight:bold;color:{AZUL}">{_e(d["nombre"])}</div>'
        f'{cargo}'
        f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">{filas}</table>'
        f'</td></tr>'
        f'{barra_redes}'
        f'</table>'
    )
