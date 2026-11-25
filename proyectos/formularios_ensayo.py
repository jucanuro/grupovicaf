"""Formulario configurable de resultados por servicio (HU-LIMS-36).

Todo ensayo se registra con el mismo flujo (Iniciar → Registrar resultados →
Revisión → Informe). Lo que cambia entre servicios son los campos del formulario:
cada servicio puede tener una ``PlantillaFormulario`` con la lista de campos del
formato en papel. Esta lista se copia («esquema») al crear el resultado, así un
cambio posterior de la plantilla no altera ensayos ya registrados.

Un campo es un dict:

    {"clave": "humedad", "etiqueta": "Contenido de humedad", "tipo": "numero",
     "unidad": "%", "requerido": true, "grupo": "Resultados", "ayuda": "…",
     "opciones": ["A", "B"]}   # opciones solo para tipo «seleccion»
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

TIPOS = {
    'numero': 'Número',
    'texto': 'Texto corto',
    'texto_largo': 'Texto largo',
    'fecha': 'Fecha',
    'si_no': 'Sí / No',
    'cumple': 'Cumple / No cumple',
    'seleccion': 'Selección',
}
_CLAVE = re.compile(r'^[a-z][a-z0-9_]{0,38}$')


def esquema_vacio():
    return {'nombre': '', 'campos': [], 'instrucciones': ''}


def validar_campos(campos):
    """Lista de errores legibles ([] = válido) de la lista de campos de una plantilla."""
    errores = []
    if not isinstance(campos, list):
        return ['Los campos deben ser una lista.']
    vistas = set()
    for i, c in enumerate(campos, 1):
        if not isinstance(c, dict):
            errores.append(f'Campo {i}: debe ser un objeto.')
            continue
        clave = c.get('clave', '')
        if not isinstance(clave, str) or not _CLAVE.match(clave):
            errores.append(f'Campo {i}: «clave» en minúsculas, números y guion bajo (ej. humedad_inicial).')
        elif clave in vistas:
            errores.append(f'Campo {i}: la clave «{clave}» está repetida.')
        vistas.add(clave)
        if not str(c.get('etiqueta', '')).strip():
            errores.append(f'Campo {i} ({clave}): falta la etiqueta.')
        if c.get('tipo') not in TIPOS:
            errores.append(f'Campo {i} ({clave}): tipo no válido. Usa: ' + ', '.join(TIPOS))
        if c.get('tipo') == 'seleccion' and not (isinstance(c.get('opciones'), list) and c['opciones']):
            errores.append(f'Campo {i} ({clave}): un campo de selección necesita «opciones».')
    return errores


def normalizar_campos(campos):
    """Copia limpia de los campos con valores por defecto (para guardar en el esquema)."""
    limpios = []
    for c in campos:
        limpios.append({
            'clave': c['clave'], 'etiqueta': str(c['etiqueta']).strip(), 'tipo': c['tipo'],
            'unidad': str(c.get('unidad', '')).strip(), 'requerido': bool(c.get('requerido', False)),
            'grupo': str(c.get('grupo', '')).strip(), 'ayuda': str(c.get('ayuda', '')).strip(),
            'opciones': [str(o) for o in c.get('opciones', [])] if c.get('tipo') == 'seleccion' else [],
        })
    return limpios


def leer_valor(campo, texto):
    """(valor, error) de lo que escribió el técnico. Vacío = (None, None)."""
    texto = (texto or '').strip()
    if texto == '':
        return None, None
    tipo = campo['tipo']
    if tipo == 'numero':
        try:
            valor = Decimal(texto.replace(',', '.'))
        except InvalidOperation:
            return None, f"«{campo['etiqueta']}» debe ser un número."
        if not valor.is_finite() or abs(valor) > Decimal('1e12'):
            return None, f"«{campo['etiqueta']}» está fuera de rango."
        return format(valor.normalize(), 'f') if valor != valor.to_integral() else str(int(valor)), None
    if tipo == 'fecha':
        try:
            fecha = datetime.strptime(texto, '%Y-%m-%d').date()
        except ValueError:
            return None, f"«{campo['etiqueta']}» debe ser una fecha válida."
        if fecha > date.today():
            return None, f"«{campo['etiqueta']}» no puede ser futura."
        return fecha.isoformat(), None
    if tipo == 'si_no':
        if texto not in ('si', 'no'):
            return None, f"«{campo['etiqueta']}»: elige Sí o No."
        return texto, None
    if tipo == 'cumple':
        if texto not in ('cumple', 'no_cumple'):
            return None, f"«{campo['etiqueta']}»: elige Cumple o No cumple."
        return texto, None
    if tipo == 'seleccion':
        if texto not in campo.get('opciones', []):
            return None, f"«{campo['etiqueta']}»: elige una de las opciones."
        return texto, None
    largo = 5000 if tipo == 'texto_largo' else 255
    return texto[:largo], None


def mostrar(campo, valor):
    """Texto legible de un valor guardado (para revisión, informe y trazabilidad)."""
    if valor in (None, ''):
        return ''
    tipo = campo['tipo']
    if tipo == 'fecha':
        try:
            return date.fromisoformat(valor).strftime('%d/%m/%Y')
        except ValueError:
            return str(valor)
    if tipo == 'si_no':
        return 'Sí' if valor == 'si' else 'No'
    if tipo == 'cumple':
        return 'Cumple' if valor == 'cumple' else 'No cumple'
    texto = str(valor)
    unidad = campo.get('unidad', '')
    return f'{texto} {unidad}'.strip() if tipo == 'numero' and unidad else texto


def faltantes(esquema, datos):
    """Etiquetas de los campos obligatorios que aún no tienen valor."""
    return [c['etiqueta'] for c in esquema.get('campos', []) if c.get('requerido') and datos.get(c['clave']) in (None, '')]


def filas(esquema, datos):
    """[(grupo, etiqueta, texto)] de lo registrado, en el orden del formulario (para revisión e informe)."""
    return [
        (c.get('grupo', ''), c['etiqueta'], mostrar(c, datos.get(c['clave'])))
        for c in esquema.get('campos', [])
    ]
