"""Trazabilidad de los resultados de ensayo: qué dato se corrigió, quién y cuándo.

Uso:

    antes = instantanea(ensayo, CAMPOS_RESULTADO)
    ... se cambian y guardan los campos ...
    anotar_cambios(ensayo, ensayo, antes, CAMPOS_RESULTADO, request.user)

Solo se anotan correcciones (el dato ya tenía valor y cambió). Los datos del
cliente de la probeta (``MuestraDetalle``) se anotan en el resultado de la
línea, con el prefijo «Probeta:».
"""
from datetime import date
from decimal import Decimal

from .models import CambioResultado, MuestraDetalle, ResultadoEnsayo

CAMPOS_RESULTADO = [
    'fecha_ensayo', *ResultadoEnsayo.CAMPOS_MEDIDOS, 'tipo_fractura', 'tipos_defecto', 'defectos',
    'verif_perpendicularidad', 'verif_planitud', 'video_grabado', 'observaciones', 'resumen',
]
CAMPOS_MUESTRA = ['codigo_cliente', 'elemento_estructural', 'fc_diseno', 'fecha_fabricacion', 'edad_ensayo_dias']


def instantanea(obj, campos):
    return {c: getattr(obj, c) for c in campos}


def texto(valor):
    """Valor legible y estable para comparar y mostrar."""
    if valor is None:
        return ''
    if isinstance(valor, bool):
        return 'Sí' if valor else 'No'
    if isinstance(valor, Decimal):
        return format(valor.normalize(), 'f') if valor == valor.to_integral() else str(valor)
    if isinstance(valor, date):
        return valor.strftime('%d/%m/%Y')
    return str(valor).strip()


def _etiqueta(modelo, campo):
    nombre = str(modelo._meta.get_field(campo).verbose_name)
    return nombre[:1].upper() + nombre[1:]


def anotar_cambios(resultado, obj, antes, campos, usuario, prefijo=''):
    """Crea un ``CambioResultado`` por cada campo que tenía valor y cambió."""
    modelo = type(obj)
    nuevos = []
    for campo in campos:
        anterior, nuevo = texto(antes.get(campo)), texto(getattr(obj, campo))
        if anterior and anterior != nuevo:
            nuevos.append(CambioResultado(
                resultado=resultado, campo=(prefijo + campo)[:40],
                etiqueta=((f"{prefijo.rstrip(':').title()}: " if prefijo else '') + _etiqueta(modelo, campo))[:80],
                anterior=anterior[:255], nuevo=nuevo[:255],
                usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
            ))
    if nuevos:
        CambioResultado.objects.bulk_create(nuevos)
    return len(nuevos)


def anotar_foto_reemplazada(resultado, etiqueta_foto, usuario):
    CambioResultado.objects.create(
        resultado=resultado, campo='foto', etiqueta=f"Foto: {etiqueta_foto}"[:80],
        anterior='foto anterior', nuevo='foto nueva',
        usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
    )


def anotar_foto_borrada(resultado, etiqueta_foto, usuario):
    CambioResultado.objects.create(
        resultado=resultado, campo='foto', etiqueta=f"Foto: {etiqueta_foto}"[:80],
        anterior='foto subida', nuevo='(borrada)',
        usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
    )


__all__ = ['CAMPOS_RESULTADO', 'CAMPOS_MUESTRA', 'instantanea', 'anotar_cambios', 'anotar_foto_reemplazada', 'anotar_foto_borrada',
           'texto', 'MuestraDetalle']
