"""Modo oscuro del LIMS: genera static/css/tema_oscuro_utilidades.css.

El LIMS pinta con clases de Tailwind por CDN (bg-white, text-slate-700...)
escritas a mano en ~80 plantillas. En vez de añadir `dark:` a cada clase, este
módulo lee las plantillas y el JS del LIMS (como hace el JIT de Tailwind),
encuentra las clases de color que se usan y escribe para cada una su versión
oscura bajo `html.dark`. Así una pantalla nueva queda oscura sin tocarla.

Reglas de la paleta oscura (contraste AA sobre la superficie #111a2b):
- Grises (slate, gray, zinc, neutral, stone, white): se invierte la escala.
  Fondos claros pasan a superficies azul pizarra; textos oscuros a claros.
- Colores (blue, emerald, rose...): los fondos 50-300 pasan a un velo
  translúcido del tono 500; los textos 500-950 suben a 200-400. Los fondos
  saturados (≥400) y los textos claros (≤400) no cambian.
- Dentro de un elemento con la clase `tema-claro` (la hoja A4 del editor de
  informes, por ejemplo) no se aplica nada: el papel sigue blanco.
- Toda clase encontrada se reescribe, aunque su color no cambie, para que la
  cascada entre clases siga igual que en modo claro (si no, `html.dark
  .bg-white` le ganaría a `hover:bg-blue-600`).

Si agregas clases de color nuevas en una plantilla, vuelve a generar:
    python manage.py generar_tema_oscuro
La prueba core.tests_tema_oscuro falla si el archivo quedó desactualizado.
"""
import re
from pathlib import Path

from django.conf import settings

SALIDA = Path('static/css/tema_oscuro_utilidades.css')

# Plantillas y JS del LIMS. La web pública (templates/web, web_*) y el correo
# (hoja propia static/correo/css/correo.css) quedan fuera.
FUENTES = (
    'templates/*.html',
    'templates/registration/*.html',
    'templates/analisis/**/*.html',
    'core/templates/**/*.html',
    'clientes/templates/**/*.html',
    'trabajadores/templates/**/*.html',
    'servicios/templates/**/*.html',
    'proyectos/templates/**/*.html',
    'actividades/templates/**/*.html',
    'analisis/templates/**/*.html',
    'vouchers/templates/**/*.html',
    'static/js/*.js',
)

# Paleta de Tailwind 3.4 (tailwindcss/colors), tono:hex.
_PALETA_TXT = {
    'slate': '50:f8fafc 100:f1f5f9 200:e2e8f0 300:cbd5e1 400:94a3b8 500:64748b 600:475569 700:334155 800:1e293b 900:0f172a 950:020617',
    'gray': '50:f9fafb 100:f3f4f6 200:e5e7eb 300:d1d5db 400:9ca3af 500:6b7280 600:4b5563 700:374151 800:1f2937 900:111827 950:030712',
    'zinc': '50:fafafa 100:f4f4f5 200:e4e4e7 300:d4d4d8 400:a1a1aa 500:71717a 600:52525b 700:3f3f46 800:27272a 900:18181b 950:09090b',
    'neutral': '50:fafafa 100:f5f5f5 200:e5e5e5 300:d4d4d4 400:a3a3a3 500:737373 600:525252 700:404040 800:262626 900:171717 950:0a0a0a',
    'stone': '50:fafaf9 100:f5f5f4 200:e7e5e4 300:d6d3d1 400:a8a29e 500:78716c 600:57534e 700:44403c 800:292524 900:1c1917 950:0c0a09',
    'red': '50:fef2f2 100:fee2e2 200:fecaca 300:fca5a5 400:f87171 500:ef4444 600:dc2626 700:b91c1c 800:991b1b 900:7f1d1d 950:450a0a',
    'orange': '50:fff7ed 100:ffedd5 200:fed7aa 300:fdba74 400:fb923c 500:f97316 600:ea580c 700:c2410c 800:9a3412 900:7c2d12 950:431407',
    'amber': '50:fffbeb 100:fef3c7 200:fde68a 300:fcd34d 400:fbbf24 500:f59e0b 600:d97706 700:b45309 800:92400e 900:78350f 950:451a03',
    'yellow': '50:fefce8 100:fef9c3 200:fef08a 300:fde047 400:facc15 500:eab308 600:ca8a04 700:a16207 800:854d0e 900:713f12 950:422006',
    'lime': '50:f7fee7 100:ecfccb 200:d9f99d 300:bef264 400:a3e635 500:84cc16 600:65a30d 700:4d7c0f 800:3f6212 900:365314 950:1a2e05',
    'green': '50:f0fdf4 100:dcfce7 200:bbf7d0 300:86efac 400:4ade80 500:22c55e 600:16a34a 700:15803d 800:166534 900:14532d 950:052e16',
    'emerald': '50:ecfdf5 100:d1fae5 200:a7f3d0 300:6ee7b7 400:34d399 500:10b981 600:059669 700:047857 800:065f46 900:064e3b 950:022c22',
    'teal': '50:f0fdfa 100:ccfbf1 200:99f6e4 300:5eead4 400:2dd4bf 500:14b8a6 600:0d9488 700:0f766e 800:115e59 900:134e4a 950:042f2e',
    'cyan': '50:ecfeff 100:cffafe 200:a5f3fc 300:67e8f9 400:22d3ee 500:06b6d4 600:0891b2 700:0e7490 800:155e75 900:164e63 950:083344',
    'sky': '50:f0f9ff 100:e0f2fe 200:bae6fd 300:7dd3fc 400:38bdf8 500:0ea5e9 600:0284c7 700:0369a1 800:075985 900:0c4a6e 950:082f49',
    'blue': '50:eff6ff 100:dbeafe 200:bfdbfe 300:93c5fd 400:60a5fa 500:3b82f6 600:2563eb 700:1d4ed8 800:1e40af 900:1e3a8a 950:172554',
    'indigo': '50:eef2ff 100:e0e7ff 200:c7d2fe 300:a5b4fc 400:818cf8 500:6366f1 600:4f46e5 700:4338ca 800:3730a3 900:312e81 950:1e1b4b',
    'violet': '50:f5f3ff 100:ede9fe 200:ddd6fe 300:c4b5fd 400:a78bfa 500:8b5cf6 600:7c3aed 700:6d28d9 800:5b21b6 900:4c1d95 950:2e1065',
    'purple': '50:faf5ff 100:f3e8ff 200:e9d5ff 300:d8b4fe 400:c084fc 500:a855f7 600:9333ea 700:7e22ce 800:6b21a8 900:581c87 950:3b0764',
    'fuchsia': '50:fdf4ff 100:fae8ff 200:f5d0fe 300:f0abfc 400:e879f9 500:d946ef 600:c026d3 700:a21caf 800:86198f 900:701a75 950:4a044e',
    'pink': '50:fdf2f8 100:fce7f3 200:fbcfe8 300:f9a8d4 400:f472b6 500:ec4899 600:db2777 700:be185d 800:9d174d 900:831843 950:500724',
    'rose': '50:fff1f2 100:ffe4e6 200:fecdd3 300:fda4af 400:fb7185 500:f43f5e 600:e11d48 700:be123c 800:9f1239 900:881337 950:4c0519',
}
PALETA = {
    familia: dict((t, '#' + h) for t, h in (par.split(':') for par in texto.split()))
    for familia, texto in _PALETA_TXT.items()
}
GRISES = ('slate', 'gray', 'zinc', 'neutral', 'stone')
ORDEN_FAMILIAS = ('black', 'white') + tuple(PALETA) + ('brand', 'surface', 'background')
TONOS = ('50', '100', '200', '300', '400', '500', '600', '700', '800', '900', '950')

# Colores propios del tailwind.config de base_vicafpro.html.
BRAND = {'50': '#eff6ff', '100': '#dbeafe', '500': '#3b82f6', '600': '#2563eb', '700': '#1d4ed8', '900': '#0f172a'}

# Escala oscura de los grises, por propiedad. 'white' es la superficie de las tarjetas.
GRIS_FONDO = {
    'white': '#111a2b', '50': '#162133', '100': '#1b273b', '200': '#243146', '300': '#2f3d54',
    '400': '#475569', '500': '#64748b', '600': '#3f4d63', '700': '#334155', '800': '#3b4a60',
    '900': '#334155', '950': '#2a3649',
}
GRIS_TEXTO = {
    'black': '#f1f5f9', '950': '#f1f5f9', '900': '#f1f5f9', '800': '#e2e8f0', '700': '#cbd5e1',
    '600': '#b6c2d2', '500': '#94a3b8', '400': '#7f8ea5', '300': '#5d6d84', '200': '#4a5a71',
    '100': '#3a4a60', '50': '#2c3a4f',
}
GRIS_BORDE = {
    'white': '#1f2b3f', '50': '#1a2538', '100': '#1f2b3f', '200': '#27354b', '300': '#334359',
    '400': '#475569',
}

# Colores arbitrarios (text-[#...]) del dashboard: equivalentes legibles en oscuro.
ARBITRARIOS = {
    '#1c5cab': '#7cb0f0', '#b42323': '#f87171', '#006300': '#4ade80', '#510b77': '#c4a1f0',
    '#2a78d6': '#5b9be6',
}

PROPIEDADES = {
    'bg': 'background-color',
    'text': 'color',
    'border': 'border-color',
    'divide': 'border-color',
    'ring': '--tw-ring-color',
    'placeholder': 'color',
    'from': None, 'via': None, 'to': None,
    'fill': 'fill',
    'stroke': 'stroke',
    'outline': 'outline-color',
}
ORDEN_PROPIEDADES = tuple(PROPIEDADES)

VARIANTES = {
    'hover': ':hover', 'focus': ':focus', 'focus-within': ':focus-within',
    'focus-visible': ':focus-visible', 'active': ':active', 'disabled': ':disabled',
    'checked': ':checked', 'first': ':first-child', 'last': ':last-child',
    'odd': ':nth-child(odd)', 'even': ':nth-child(even)', 'placeholder': '::placeholder',
}
ANCESTROS = {'group-hover': '.group:hover ', 'group-focus': '.group:focus ', 'group-focus-within': '.group:focus-within '}
HERMANOS = {'peer-checked': '.peer:checked ~ ', 'peer-focus': '.peer:focus ~ '}
PANTALLAS = {'sm': 640, 'md': 768, 'lg': 1024, 'xl': 1280, '2xl': 1536}

_COLOR = r'(?:black|white|transparent|brand|surface|background|' + '|'.join(PALETA) + r')'
CLASE_RE = re.compile(
    r'(?<![\w\-:/\[])'
    r'((?:[a-z0-9-]+:)*)'
    r'(bg|text|border|divide|ring|placeholder|from|via|to|fill|stroke|outline)'
    r'-(?:(' + _COLOR + r')(?:-(50|[1-9]00|950))?|\[(#[0-9a-fA-F]{6})\])'
    r'(?:/(\d{1,3}))?'
    r'(?![\w\-\[])'
)


def _rgb(hexa):
    hexa = hexa.lstrip('#')
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def _rgba(hexa, alfa):
    r, g, b = _rgb(hexa)
    alfa = round(alfa, 3)
    if alfa >= 1:
        return f'rgb({r} {g} {b})'
    return f'rgb({r} {g} {b} / {alfa:g})'


def _claro(familia, tono):
    """Color original (modo claro) de la clase, o None si no aplica."""
    if familia == 'black':
        return '#000000'
    if familia in ('white', 'surface'):
        return '#ffffff'
    if familia == 'background':
        return '#f8fafc'
    if familia == 'brand':
        return BRAND.get(tono)
    return PALETA.get(familia, {}).get(tono)


def color_oscuro(prop, familia, tono, alfa):
    """Devuelve (color_css) para modo oscuro. alfa en 0-1 (1 = opaco)."""
    if familia == 'transparent':
        return 'transparent'
    if familia == 'brand':
        familia = 'slate' if tono == '900' else 'blue'
    elif familia == 'surface':
        familia = 'white'
    elif familia == 'background':
        familia, tono = 'slate', '50'
    original = _claro(familia, tono)
    if original is None:
        return None
    grupo = 'fondo' if prop in ('bg', 'from', 'via', 'to') else 'texto' if prop in ('text', 'placeholder', 'fill', 'stroke') else 'borde'

    if familia in ('white', 'black') or familia in GRISES:
        clave = familia if familia in ('white', 'black') else tono
        # Velos blancos casi transparentes (bg-white/10 sobre fondos oscuros) y
        # todo lo que ya es oscuro se quedan como están.
        if familia == 'white' and alfa <= 0.3:
            return _rgba(original, alfa)
        tabla = {'fondo': GRIS_FONDO, 'texto': GRIS_TEXTO, 'borde': GRIS_BORDE}[grupo]
        if prop == 'ring':
            tabla = GRIS_BORDE
        if familia == 'white' and grupo == 'texto':
            return _rgba(original, alfa)
        nuevo = tabla.get(clave)
        if nuevo is None or (familia in GRISES and grupo == 'fondo' and alfa <= 0.6 and tono in ('800', '900', '950')):
            return _rgba(original, alfa)  # velos oscuros (overlays): sin cambio
        return _rgba(nuevo, alfa)

    # Familias de color.
    tonos = PALETA[familia]
    n = int(tono)
    if grupo == 'fondo':
        velo = {50: 0.12, 100: 0.18, 200: 0.26, 300: 0.40}.get(n)
        if velo is None:
            return _rgba(original, alfa)
        return _rgba(tonos['400'] if n == 300 else tonos['500'], velo * alfa)
    if grupo == 'texto':
        nuevo = {950: '200', 900: '200', 800: '200', 700: '300', 600: '400', 500: '400'}.get(n)
        return _rgba(tonos[nuevo] if nuevo else original, alfa)
    if prop == 'ring':
        return _rgba(original, alfa)
    velo = {50: 0.18, 100: 0.25, 200: 0.35, 300: 0.5}.get(n)
    if velo is None:
        return _rgba(original, alfa)
    return _rgba(tonos['500'], velo * alfa)


def _escapar(clase):
    return re.sub(r'([^a-zA-Z0-9_-])', r'\\\1', clase)


def _regla(variantes, prop, valor, clase):
    """Arma (media, selector, declaraciones) o None si hay una variante desconocida."""
    media = None
    pseudo = ''
    previo = ''
    for v in variantes:
        if v in PANTALLAS:
            media = PANTALLAS[v]
        elif v in VARIANTES:
            pseudo += VARIANTES[v]
        elif v in ANCESTROS:
            previo = ANCESTROS[v]
        elif v in HERMANOS:
            previo = HERMANOS[v]
        elif v == 'dark':
            pass
        else:
            return None
    # :not(.tema-claro *) deja en claro las «hojas de papel» (vista del
    # informe A4, vistas previas de impresión), que se marcan con .tema-claro.
    sel = f'html.dark {previo}.{_escapar(clase)}:not(.tema-claro *)'
    if prop == 'divide':
        sel += f'{pseudo} > :not([hidden]) ~ :not([hidden])'
    elif prop == 'placeholder':
        sel += f'{pseudo}::placeholder'
    else:
        sel += pseudo
    if prop == 'from':
        decl = (f'--tw-gradient-from: {valor} var(--tw-gradient-from-position); '
                f'--tw-gradient-to: transparent var(--tw-gradient-to-position); '
                f'--tw-gradient-stops: var(--tw-gradient-from), var(--tw-gradient-to)')
    elif prop == 'via':
        decl = (f'--tw-gradient-to: transparent var(--tw-gradient-to-position); '
                f'--tw-gradient-stops: var(--tw-gradient-from), {valor} var(--tw-gradient-via-position), var(--tw-gradient-to)')
    elif prop == 'to':
        decl = f'--tw-gradient-to: {valor} var(--tw-gradient-to-position)'
    else:
        decl = f'{PROPIEDADES[prop]}: {valor}'
    return media, sel, decl


def recolectar(base=None):
    """Clases de color usadas en el LIMS: {clase: (variantes, prop, familia, tono, hex, alfa)}."""
    base = Path(base or settings.BASE_DIR)
    encontradas = {}
    for patron in FUENTES:
        for archivo in sorted(base.glob(patron)):
            texto = archivo.read_text(encoding='utf-8', errors='ignore')
            for m in CLASE_RE.finditer(texto):
                variantes, prop, familia, tono, hexa, alfa = m.groups()
                clase = m.group(0)
                encontradas[clase] = (
                    tuple(v for v in variantes.split(':') if v), prop, familia, tono, hexa,
                    int(alfa) / 100 if alfa else 1.0,
                )
    return encontradas


def _orden(item):
    clase, (variantes, prop, familia, tono, hexa, alfa) = item
    return (
        len(variantes), tuple(PANTALLAS.get(v, 0) for v in variantes), ORDEN_PROPIEDADES.index(prop),
        ORDEN_FAMILIAS.index(familia) if familia in ORDEN_FAMILIAS else len(ORDEN_FAMILIAS),
        TONOS.index(tono) if tono in TONOS else -1, alfa, clase,
    )


def generar_css(base=None):
    reglas = []
    medias = {}
    for clase, (variantes, prop, familia, tono, hexa, alfa) in sorted(recolectar(base).items(), key=_orden):
        if hexa:
            valor = ARBITRARIOS.get(hexa.lower())
            if not valor:
                continue
            valor = _rgba(valor, alfa)
        else:
            if familia in GRISES + tuple(PALETA) and tono is None:
                continue
            if familia in ('brand',) and tono not in BRAND:
                continue
            valor = color_oscuro(prop, familia, tono or '500', alfa)
            if valor is None:
                continue
        regla = _regla(variantes, prop, valor, clase)
        if regla is None:
            continue
        media, sel, decl = regla
        linea = f'{sel} {{ {decl}; }}'
        if media:
            medias.setdefault(media, []).append('    ' + linea)
        else:
            reglas.append(linea)
    partes = [
        '/* GENERADO por `python manage.py generar_tema_oscuro` (core/tema_oscuro.py).',
        '   No editar a mano: los ajustes van en static/css/tema_oscuro.css. */',
        *reglas,
    ]
    for ancho in sorted(medias):
        partes.append(f'@media (min-width: {ancho}px) {{')
        partes.extend(medias[ancho])
        partes.append('}')
    return '\n'.join(partes) + '\n'
