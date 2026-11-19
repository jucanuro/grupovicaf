"""Lee el CSV de cuentas de correo (direccion;nombre;accesos) y devuelve lo que espera cada usuario."""
import csv
from collections import OrderedDict
from pathlib import Path

from django.core.management.base import CommandError


def esperado_por_usuario(ruta):
    """{usuario: [(direccion, rol), ...]} en el orden del archivo."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise CommandError(f'No existe {ruta}')
    resultado = OrderedDict()
    with ruta.open(encoding='utf-8-sig', newline='') as f:
        for fila in csv.DictReader(f, delimiter=';'):
            direccion = (fila.get('direccion') or '').strip().lower()
            for par in (fila.get('accesos') or '').split(','):
                usuario, _, rol = par.strip().partition(':')
                if direccion and usuario.strip():
                    resultado.setdefault(usuario.strip(), []).append((direccion, rol.strip() or 'gestiona'))
    return resultado
