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

AZUL = '#1E3A8A'
AZUL_CLARO = '#6B9AD8'
GRIS = '#334155'

CAMPOS_TEXTO = (
    ('nombre', 'Nombre', 80),
    ('cargo', 'Cargo', 80),
    ('telefono', 'Teléfono', 40),
    ('correo', 'Correo', 120),
    ('direccion', 'Dirección', 120),
    ('ciudad', 'Ciudad', 80),
)
CAMPOS_REDES = (
    ('web', 'Web', 'W'),
    ('facebook', 'Facebook', 'f'),
    ('instagram', 'Instagram', 'ig'),
    ('linkedin', 'LinkedIn', 'in'),
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
             'direccion': '', 'ciudad': '', 'web': '', 'facebook': '', 'instagram': '', 'linkedin': ''}
    if n:
        datos.update(telefono=n.telefono, direccion=n.direccion_calle, ciudad=n.direccion_localidad,
                     web=settings.SITE_URL if settings.SITE_URL.startswith('https://') else '',
                     facebook=n.facebook_url, instagram=n.instagram_url, linkedin=n.linkedin_url)
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


def _fila(texto, enlace=None):
    if not texto:
        return ''
    contenido = _e(texto)
    if enlace:
        contenido = f'<a href="{_e(enlace)}" style="color:{GRIS};text-decoration:none">{contenido}</a>'
    return (f'<tr><td style="padding:1px 0;font-family:Arial,Helvetica,sans-serif;font-size:13px;'
            f'line-height:18px;color:{GRIS}">{contenido}</td></tr>')


def _insignia(enlace, marca, etiqueta):
    """Círculo con la marca de la red. Es una celda (no un <a> en línea) porque
    el sanitizador no admite display y el tamaño solo vale en celdas."""
    return (f'<td width="24" height="24" align="center" valign="middle" bgcolor="{AZUL}" '
            f'style="width:24px;height:24px;border-radius:12px;background-color:{AZUL};text-align:center">'
            f'<a href="{_e(enlace)}" title="{_e(etiqueta)}" style="color:#ffffff;text-decoration:none;'
            f'font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:bold">{_e(marca)}</a></td>'
            f'<td width="4" style="width:4px"></td>')


def generar_html(datos):
    """HTML de la firma (ya listo para pasar por sanitizar_html)."""
    d = datos
    ubicacion = ', '.join(p for p in (d['direccion'], d['ciudad']) if p)
    redes = ''.join(_insignia(d[c], m, e) for c, e, m in CAMPOS_REDES if d[c])
    filas = ''.join((
        _fila(d['telefono'], f"tel:{re.sub(r'[^0-9+]', '', d['telefono'])}" if re.search(r'\d', d['telefono']) else None),
        _fila(d['correo'], f"mailto:{d['correo']}" if '@' in d['correo'] else None),
        _fila(ubicacion),
    ))
    cargo = (f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:18px;'
             f'color:{AZUL_CLARO};padding-bottom:4px">{_e(d["cargo"])}</div>') if d['cargo'] else ''
    columna_redes = (f'<td valign="middle" align="right" style="padding:0 0 0 16px">'
                     f'<table cellpadding="0" cellspacing="0" border="0"><tr>{redes}</tr></table></td>'
                     if redes else '')
    return (
        f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;margin-top:12px">'
        f'<tr>'
        f'<td valign="middle" style="padding:4px 16px 4px 0;border-right:3px solid {AZUL_CLARO}">'
        f'<img src="{_e(url_logo())}" alt="Grupo VICAF" width="120" style="width:120px;height:auto">'
        f'</td>'
        f'<td valign="middle" style="padding:0 16px">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:17px;line-height:22px;font-weight:bold;'
        f'color:{AZUL}">{_e(d["nombre"])}</div>'
        f'{cargo}'
        f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">{filas}</table>'
        f'</td>'
        f'{columna_redes}'
        f'</tr></table>'
    )
