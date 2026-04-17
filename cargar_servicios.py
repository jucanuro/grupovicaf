#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import django
from decimal import Decimal, InvalidOperation
from django.db import transaction

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grupovicaf.settings.dev")
django.setup()

from servicios.models import Servicio, Norma, Metodo


# ==========================================
# DATA PEGADA
# Formato:
# codigo_facturacion \t nombre \t norma \t metodo \t precio \t unidad
# ==========================================
DATA = r"""
CE001	Comprobación de tamices Serie gruesa	ASTM E11-24		50	Und
CE002	Comprobación de tamices Serie fina hasta malla 200	ASTM E11-24		70	Und
CE003	Comprobación de humedómetro - Speedy			80	Und
CE004	Comprobación de Copa de Casagrande y ranurador	ASTM D4318-17e1		80	Und
CN001	Estudio de mecánica de suelos con fines de diseño de cimentaciones (R)	Varias		0	EMS
CN002	Estudio de mecánica de suelos con fines de diseño de pavimentos (R)	Varias		0	EMS
CN003	Estudio de mecánica de suelos con fines de diseño de instalaciones sanitarias de agua y alcantarillado (R)			0	EMS
CN004	Estudio de mecánica de suelos con fines de Estabilidad de Taludes (R)			0	Ensayo
CN005	Estudio y Evaluación de Canteras y fuentes de agua (R)	Varias		0	E
CN006	Estudio y Evaluación de Estructuras existentes de concreto simple o armado (R)	Varias		0	E
CN007	Diseño de mezclas - TEÓRICO	A solicitud del cliente		450	DM
CN008	Diseño de mezclas - TEÓRICO con o sin aditivos (Incluye: Ensayos Físicos: A. Granulométrico, P. Específico, P. Unitario, C. de Humedad), no incluye insumos.	ACI		500	DM
CN009	Diseño de mezclas - COMPROBADO con o sin aditivos (Incluye: Ensayos Físicos: A. Granulométrico, P. Específico, P. Unitario, C. de Humedad), Ensayos de Control de Calidad (Slump, PUC, temperatura del concreto, resistencia a la compresión a 3 y 7 días), no incluye insumos.	ACI		800	DM
EA001	Análisis granulométrico (Glb) / Análisis granulométrico (G) / Análisis granulométrico (F)	ASTM C136/C136M-19		70	Ensayo
EA002	Contenido de Humedad	ASTM C566-19		25	Ensayo
EA003	Peso unitario suelto y varillado	ASTM C29/C29M-23	A / B / C	60	Ensayo
EA004	Gravedad Específica y absorción (A. grueso) Ensayo necesario para la corrección del proctor	ASTM C127-24		90	Ensayo
EA005	Gravedad Específica y absorción (A. fino)	ASTM C128-22		90	Ensayo
EA006	Material más fino que el tamiz No. 200 por lavado	ASTM C117-23		50	Ensayo
EA007	Partículas chatas y alargadas	ASTM D4791-19 (2023)	Conteo / Masa	90	Ensayo
EA008	Partículas fracturadas	ASTM D5821-13(2017)	Conteo / Masa	90	Ensayo
EA009	Terrones de arcilla y partículas friables	ASTM C142/C142M-17(2023)		60	Ensayo
EA010	Abrasión por medio de la máquina de los ángeles (T.M < 1 1/2") (1)	ASTM C131/C131M-20		200	Ensayo
EA011	Abrasión por medio de la máquina de los ángeles (T.M > 3/4") (1)	ASTM C535-16 (Reaprobada 2024)		250	Ensayo
EA012	Equivalente de arena de suelos y agregados	ASTM D2419-22		90	Ensayo
EA013	Impurezas orgánicas en el agregado fino - Método cualitativo	ASTM C40/C40M-20		50	Ensayo
EA014	Índice de aplanamiento y alargamiento	MTC E221		90	Ensayo
EC001	Resistencia a la compresión de probetas cilíndricas de concreto	ASTM C39/C39M-24		25	Ensayo
EC002	Resistencia a la compresión de especímenes de mortero	ASTM C109/C109M-24		25	Ensayo
EDC001	Test de percolación (R)	IS.020		0	Ensayo
EDC002	Densidad mediante el cono y la arena	NTP 339.143 1999 (revisada el 2019)		65	Ensayo
EDC003	Contenido de humedad (SPEEDY) (mín. 4 puntos) (R)	ASTM D4944-25		15	Ensayo
EDC004	Medición de asentamiento del concreto con el cono de Abrams (R)	ASTM C143/C143-20		40	Ensayo
EDC005	Medición de la temperatura del concreto fresco (R)	ASTM C1064/C1064M-23		15	Ensayo
EDC006	Toma de muestra de concreto (R)	ASTM C31/C31M-25a		25	Ensayo
EDC007	Esclerometría (R)	ASTM C805/C805M-18		45	Ensayo
EDC008	Extracción de núcleos de concreto con diamantina Incluye tallado	ASTM C42/C42M-20		280	Ensayo
EDC009	Resistividad del suelo (R)			0	Ensayo
EDC010	Medición de pozo tierra (R)			0	Ensayo
EE001	Corte Directo (1)	ASTM D3080/D3080-23		450	Ensayo
EE002	Compresión Triaxial No Consolidada - No Drenada (UU) , f=2,8"	ASTM D2850-25		600	Ensayo
EE003	Compresión Triaxial No Consolidada - No Drenada (UU) , f=4"	ASTM D2850-25		650	Ensayo
EE005	Compresión Triaxial Consolidada No Drenada (CU), f=2,8"	ASTM D4767-11(2020)		1400	Ensayo
EE006	Compresión Triaxial Consolidada No Drenada (CU), f=4"	ASTM D4767-11(2020)		1700	Ensayo
EE008	Compresión Triaxial Consolidada Drenada (CD), f=2,8"	ASTM D7181-20		2000	Ensayo
EE009	Compresión Triaxial Consolidada Drenada (CD), f=4"	ASTM D7181-20		2500	Ensayo
EE011	Consolidación Unidimensional	ASTM D2435/D2435M-11 (2020)		400	Ensayo
EE012	Compresión Simple	ASTM D2166/D2166M-24		180	Ensayo
EG001	Sondeo Eléctrico Vertical (SEV) (1)	ASTM G57-20		0	Ensayo
EG002	Tomografía Eléctrica 2D (1)	ASTM D6431-18		0	Ensayo
EG003	Tomografía Eléctrica 3D (1)	ASTM D6431-18		0	Ensayo
EG004	Refracción Sísmica 2D (1)	ASTM D5777-18		0	Ensayo
EG005	Refracción Sísmica 3D (1)	ASTM D5777-18		0	Ensayo
EG006	MASW 1D (1)	ASTM D5777-18		0	Ensayo
EG007	MASW 2D (1)	ASTM D5777-18		0	Ensayo
EG008	MAM o REMI (1)	ASTM D5777-18		0	Ensayo
EQ001	Sulfatos Solubles en suelos y agua subterránea	NTP 339.178		70	Ensayo
EQ002	Cloruros en suelos y agua subterránea	NTP 339.177		70	Ensayo
EQ003	pH en suelos y agua subterránea	NTP 339.176		70	Ensayo
EQ004	Sales Solubles en suelos y agua subterránea	NTP 339.152		70	Ensayo
EQ005	Partículas Livianas (Carbón o Lignito)	ASTM C123/C123M-23		400	Ensayo
EQ006	Durabilidad con sulfato de magnesio o sodio en agregados	ASTM C88/C88M-24		380	Ensayo
EQ007	ABA Testing (potencial generador de acidez)			800	Ensayo
EQ008	Índice de Durabilidad (1)	ASTM D3744/D3744M-18		0	Ensayo
EQ009	Azul de Metileno	AASHTO TP330-07 (2019)		350	Ensayo
EQ010	Carbonatos			0	Ensayo
EQ011	Reactividad de agregados (fino y grueso)	ASTM C289-07		250	Ensayo
EQ012	Contenido de Materia Orgánica (pérdida por ignición)	ASTM D2974-25		250	Ensayo
EQ013	Sólidos en suspensión	ASTM D5907-18		80	Ensayo
EQ014	Conductividad eléctrica y resistividad (agua)	ASTM D1125-23		120	Ensayo
ER001	Propiedades Físicas (Humedad, Densidad, Peso Específico, Absorción, Porosidad)	ASTM C97/C97M-25		280	Ensayo
ER002	Corte y Tallado de Especímenes de roca			0	Ensayo
ER003	Carga puntual	ASTM D5731-16		0	Ensayo
ES001	Contenido de Humedad	ASTM D2216-19	A / B	25	Ensayo
ES002	Análisis Granulométrico por tamizado	ASTM D6913/D6913M-17		70	Ensayo
ES003	Límite Líquido, Límite Plástico e Índice de Plasticidad	ASTM D4318-17e1	A / B	70	Ensayo
ES004	Limite de Contracción	D4272/D4272M-23		50	Ensayo
ES005	Clasificación SUCS (Teórico)	ASTM D2487-17(Reaprobada 2025)		10	Ensayo
ES006	Clasificación AASHTO (Teórico)	ASTM D3282-24		10	Ensayo
ES007	Gravedad Específica de sólidos	ASTM D854-23	A / B	40	Ensayo
ES008	Peso volumétrico de suelo cohesivo	ASTM D7263-21		50	Ensayo
ES009	Proctor Estándar	ASTM D698-12 (Reaprobada 2021)	A / B / C	90	Ensayo
ES010	Proctor Modificado	ASTM D1557-12 (Reaprobada 2021)	A / B / C	120	Ensayo
ES011	CBR	ASTM D1883-21		320	Ensayo
EUA001	Resistencia a la compresión de ladrillos	NTP 331.021		25	Ensayo
EUA002	Resistencia a la compresión de unidades de albañilería de concreto (incluye refrentado)	NTP 399.604		25	Ensayo
EUA003	Absorción de unidades de albañilería de concreto	NTP 399.604		25	Ensayo
EUA004	Resistencia a la compresión de unidades de albañilería de arcilla (incluye refrentado)	NTP 339.613		25	Ensayo
EUA005	Absorción de unidades de albañilería de arcilla	NTP 339.613		25	Ensayo
EUA006	Alabeo de unidades de albañilería de arcilla	NTP 339.613		25	Ensayo
EUA007	Succión de unidades de albañilería de arcilla	NTP 339.613		25	Ensayo
EUA008	Variación dimensional de unidades de albañilería de arcilla	NTP 331.017		25	Ensayo
EUA009	Construcción de prismas de albañilería (pilas) (incluye resistencia a la compresión)	NTP 339.605		80	Ensayo
EUA010	Resistencia a la compresión de prismas de albañilería (pilas)	NTP 339.605		25	Ensayo
TC001	Excavación de calicatas (hasta 1,50 m de profundidad o hasta alcanzar el estrato rocoso)			0	Und
TC002	Excavación de calicatas (hasta 3,00 m de profundidad o hasta alcanzar el estrato rocoso)			0	Und
TC003	Toma de muestras alteradas e inalteradas	ASTM D420-18		0	Und
TC004	Descripción de Perfil Estratigráfico	ASTM D2488-17e1		0	Und
"""


def limpiar_texto(valor):
    if valor is None:
        return ""
    texto = str(valor).replace("\xa0", " ").replace("\n", " ").strip()
    texto = re.sub(r"\s+", " ", texto)
    if texto in {"-", "None", "none", "nan"}:
        return ""
    return texto


def limpiar_decimal(valor):
    valor = limpiar_texto(valor)
    if not valor:
        return Decimal("0.00")

    valor = valor.replace(",", ".")
    valor = re.sub(r"[^\d.]", "", valor)

    if not valor:
        return Decimal("0.00")

    try:
        return Decimal(valor).quantize(Decimal("0.00"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def normalizar_unidad(valor):
    unidad = limpiar_texto(valor)
    return unidad or "Ensayo"


def get_or_create_norma(valor_norma):
    valor_norma = limpiar_texto(valor_norma)
    if not valor_norma:
        return None

    obj, _ = Norma.objects.get_or_create(
        codigo=valor_norma,
        defaults={"nombre": valor_norma}
    )

    # por si existía con nombre vacío o distinto
    cambios = False
    if getattr(obj, "nombre", "") != valor_norma:
        obj.nombre = valor_norma
        cambios = True
    if getattr(obj, "codigo", "") != valor_norma:
        obj.codigo = valor_norma
        cambios = True
    if cambios:
        obj.save()

    return obj


def get_or_create_metodo(valor_metodo):
    valor_metodo = limpiar_texto(valor_metodo)
    if not valor_metodo:
        return None

    obj, _ = Metodo.objects.get_or_create(
        codigo=valor_metodo,
        defaults={"nombre": valor_metodo}
    )

    cambios = False
    if getattr(obj, "nombre", "") != valor_metodo:
        obj.nombre = valor_metodo
        cambios = True
    if getattr(obj, "codigo", "") != valor_metodo:
        obj.codigo = valor_metodo
        cambios = True
    if cambios:
        obj.save()

    return obj


def parsear_linea(linea):
    partes = linea.split("\t")

    while len(partes) < 6:
        partes.append("")

    codigo_facturacion = limpiar_texto(partes[0])
    nombre = limpiar_texto(partes[1])
    norma_txt = limpiar_texto(partes[2])
    metodo_txt = limpiar_texto(partes[3])
    precio_txt = limpiar_texto(partes[4])
    unidad_txt = limpiar_texto(partes[5])

    return {
        "codigo_facturacion": codigo_facturacion,
        "nombre": nombre,
        "norma_txt": norma_txt,
        "metodo_txt": metodo_txt,
        "precio_base": limpiar_decimal(precio_txt),
        "unidad_base": normalizar_unidad(unidad_txt),
    }


def cargar_servicios():
    lineas = [l.strip() for l in DATA.strip().splitlines() if l.strip()]

    creados = 0
    eliminados = 0
    errores = 0

    for i, linea in enumerate(lineas, start=1):
        try:
            data = parsear_linea(linea)

            codigo_facturacion = data["codigo_facturacion"]
            nombre = data["nombre"]

            if not codigo_facturacion:
                print(f"[ERROR] Línea {i}: sin código de facturación")
                errores += 1
                continue

            if not nombre:
                print(f"[ERROR] Línea {i}: sin nombre")
                errores += 1
                continue

            norma = get_or_create_norma(data["norma_txt"])
            metodo = get_or_create_metodo(data["metodo_txt"])

            with transaction.atomic():
                existente = Servicio.objects.filter(
                    codigo_facturacion=codigo_facturacion
                ).first()

                if existente:
                    existente.delete()
                    eliminados += 1
                    print(f"[DELETE] {codigo_facturacion} eliminado para recarga limpia")

                Servicio.objects.create(
                    codigo_facturacion=codigo_facturacion,
                    nombre=nombre,
                    norma=norma,
                    metodo=metodo,
                    precio_base=data["precio_base"],
                    unidad_base=data["unidad_base"],
                    esta_acreditado=True,
                )

                creados += 1
                print(f"[OK] {codigo_facturacion} - {nombre}")

        except Exception as e:
            errores += 1
            print(f"[ERROR] Línea {i}: {e}")

    print("\n" + "=" * 60)
    print("RESUMEN DE CARGA")
    print("=" * 60)
    print(f"Creados:   {creados}")
    print(f"Eliminados:{eliminados}")
    print(f"Errores:   {errores}")
    print("=" * 60)


if __name__ == "__main__":
    cargar_servicios()