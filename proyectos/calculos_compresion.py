"""Cálculos del ensayo de compresión de probetas cilíndricas (ASTM C39).

Replican el informe real VCF-INF-2026-4582 (FOR-039 v17), verificado con sus
tres probetas (RN-C01 a RN-C06 de VCF-LIMS_HU_CU_compresion):

- Diámetro promedio = (D1 + D2) / 2, redondeado a 0,25 mm.
- Longitud promedio = (L1 + L2 + L3) / 3, a 0,01 mm.
- Área = π · D² / 4 con π = 3,1416 (como la hoja del laboratorio), a 0,01 mm².
- L/D a 0,01; factor 1,00 si L/D > 1,75, si no el de la tabla de ASTM C39.
- Resistencia (MPa) = carga (kN) · 1000 / área · factor, a 0,1.
- Resistencia (kg/cm²) = MPa YA redondeado · 10,1972, a 0,1.
- % obtenido = kg/cm² / f'c · 100, entero.
- Densidad (kg/m³) = masa / (área · longitud), redondeada a 10.

``static/js/compresion_calculos.js`` hace lo mismo en el navegador; si se
cambia una regla aquí hay que cambiarla también allí.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MPA_A_KGCM2 = Decimal('10.1972')
# La hoja del laboratorio usa π = 3,1416: con él salen 8 171,30 / 8 251,61 /
# 8 211,41 mm², las áreas impresas en VCF-INF-2026-4582.
PI = Decimal('3.1416')

# ASTM C39: factor de corrección para L/D ≤ 1,75 (se interpola entre filas).
TABLA_FACTOR_LD = [
    (Decimal('1.00'), Decimal('0.87')),
    (Decimal('1.25'), Decimal('0.93')),
    (Decimal('1.50'), Decimal('0.96')),
    (Decimal('1.75'), Decimal('0.98')),
]
LD_MINIMO = Decimal('1.00')
LD_SIN_CORRECCION = Decimal('1.75')


class DatosInsuficientes(ValueError):
    pass


def _q(valor, paso):
    return Decimal(valor).quantize(Decimal(paso), rounding=ROUND_HALF_UP)


def factor_correccion(relacion_ld):
    if relacion_ld > LD_SIN_CORRECCION:
        return Decimal('1.00')
    if relacion_ld < LD_MINIMO:
        raise DatosInsuficientes("La relación L/D es menor que 1,00: la norma no admite el ensayo.")
    for (ld_a, f_a), (ld_b, f_b) in zip(TABLA_FACTOR_LD, TABLA_FACTOR_LD[1:]):
        if ld_a <= relacion_ld <= ld_b:
            f = f_a + (f_b - f_a) * (relacion_ld - ld_a) / (ld_b - ld_a)
            return _q(f, '0.01')
    return TABLA_FACTOR_LD[-1][1]


@dataclass
class Resultado:
    diametro_prom: Decimal
    longitud_prom: Decimal
    area: Decimal
    relacion_ld: Decimal
    factor: Decimal
    resistencia_mpa: Decimal
    resistencia_kgcm2: Decimal
    porcentaje: Decimal | None
    densidad: Decimal | None


def calcular(d1, d2, l1, l2, l3, carga_kn, masa_g=None, fc_kgcm2=None):
    valores = [d1, d2, l1, l2, l3, carga_kn]
    if any(v is None for v in valores):
        raise DatosInsuficientes("Faltan medidas o la carga máxima.")
    d1, d2, l1, l2, l3, carga_kn = (Decimal(str(v)) for v in valores)
    if min(d1, d2, l1, l2, l3, carga_kn) <= 0:
        raise DatosInsuficientes("Las medidas y la carga deben ser mayores que cero.")

    diametro = (((d1 + d2) / 2) * 4).quantize(Decimal('1'), rounding=ROUND_HALF_UP) / 4
    diametro = _q(diametro, '0.01')
    longitud = _q((l1 + l2 + l3) / 3, '0.01')
    area = _q(PI * diametro * diametro / 4, '0.01')
    relacion_ld = _q(longitud / diametro, '0.01')
    factor = factor_correccion(relacion_ld)
    mpa = _q(carga_kn * 1000 / area * factor, '0.1')
    kgcm2 = _q(mpa * MPA_A_KGCM2, '0.1')

    porcentaje = None
    if fc_kgcm2:
        porcentaje = _q(kgcm2 / Decimal(str(fc_kgcm2)) * 100, '1')

    densidad = None
    if masa_g:
        kg_m3 = Decimal(str(masa_g)) / (area * longitud) * Decimal('1000000')
        densidad = _q(kg_m3 / 10, '1') * 10

    return Resultado(diametro, longitud, area, relacion_ld, factor, mpa, kgcm2, porcentaje, densidad)
