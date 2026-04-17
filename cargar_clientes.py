#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import django
from pathlib import Path


def detectar_settings_desde_manage():
    manage_path = Path(__file__).resolve().parent / "manage.py"
    if not manage_path.exists():
        raise FileNotFoundError("No se encontró manage.py en esta carpeta.")

    content = manage_path.read_text(encoding="utf-8")
    match = re.search(
        r"os\.environ\.setdefault\(\s*['\"]DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
        content
    )
    if not match:
        raise ValueError("No se pudo detectar DJANGO_SETTINGS_MODULE desde manage.py")

    return match.group(1)


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grupovicaf.settings.dev")
django.setup()

from clientes.models import Cliente  # noqa: E402


DATA = r"""
GRUPO VICAF SAC	20609464632	-	Frank Gonzales Vásquez	Gerente	949923568	-	-
América construcciones SRL	20496103867	-	Claudia Riojas Ortiz	Gerente	938172121	-	-
Minería y Maquinaria JLC SRL	20600835565	-	-	Gerente	-	-	-
Concel SAC	20496188595	-	Irving Denker Sánchez Márquez	Gerente	925963734	-	-
Biler Esmith	-	-	Biler Esmith	Gerente	931651299	-	-
GESTORA DE SERVICIOS VIALES SA	20602988024	-	Ricsy Rojas	Gerente	965635927	-	-
CONSORCIO SAN VICENTE	20610044698	-	Gerson Renato	Gerente	938352754	-	-
VEGA MONTOYA ISRAEL NAPOLEON	10266331709	-	Jorge Vega	Gerente	931199943	-	-
CCA PERU	20529325488	-	-	Gerente	978374486	-	-
CONSTRUCTORA ZUMAWI POLO SAC	20559771270	-	Jhoan Polon	Gerente	956270056	-	-
MARIBEL VILLANUEVA	10758159073	-	MARIBEL VILLANUEVA	Gerente	990599028	-	-
JOSE ERNESTO ACOSTA GALVEZ E.I.R.L.	20610118021	-	JOSE ACOSTA	Gerente	974602554	-	-
Hamlet Manuel Sánchez Ambrosio	-	-	Hamlet Manuel Sánchez Ambrosio	Gerente	997141778	-	-
Glenda Fabiana Bringas Apaza	10727840023	-	Glenda Fabiana Bringas Apaza	Gerente	971564560	-	-
Paolo León	10738761281	-	Paolo León	Gerente	987567195	-	-
CEYCA	20311227913	-	Rosario Ascurra	Gerente	969714855	-	-
SRA. CAROL ABANTO	-	-	SRA. CAROL ABANTO	Gerente	997082136	-	-
ARISTOS ABC	20529523956	-	Alex Basauri	Gerente	976918161	-	-
HIDRANDINA S.A.	20132023540	-	Marco Murga Gutierrez	Gerente	949218303	-	-
STRACON	20546121250	-	Denisse Bringas	Gerente	913232325	-	-
BRIDY PEREZ	-	-	BRIDY PEREZ	Gerente	967278238	-	-
Eva Angelina Bazán Hernandez	-	-	Eva Angelina Bazán Hernandez	Gerente	-	-	-
GOBIERNO REGIONAL DE CAJAMARCA	20453744168	-	Jhonathan Figueroa Gonzales (Adquisiciones)	Gerente	928127947	-	-
JRTV E.I.R.L	20610136045	-	Ing. Julio Rafael Terrones Vásquez	Gerente	955879836	-	-
CONSORCIO CAPULI	20605418032	-	Arq. Álvaro Luis Cala Rivera	Gerente	915373936	-	-
PERÚ INFINITO SAC	20538531023	-	Yeniver Cerna	Gerente	974125838	-	-
RYQ RONALD ARTURO YOPLA CULQUI	-	-	Arq. Gloria	Gerente	948248583	-	-
Dante Alex Quiroz Cabanillas	-	-	Dante Alex Quiroz Cabanillas	Gerente	926473635	-	-
Fray Yanapa	-	-	Fray Yanapa	Gerente	976224722	-	-
JUAN VALDIVIA RAMOS	-	-	JUAN VALDIVIA RAMOS	Gerente	-	-	-
CORPORACION WOLDERS	20603641991	-	Carlos Robles Villegas	Gerente	985620356	-	-
Jhonatan Luis Gómez Terán	-	-	Jhonatan Luis Gómez Terán	Gerente	933833902	-	-
Emerson Perez Estela	-	-	Emerson Perez Estela	Gerente	915127045	-	-
CORREA INGENIEROS CONSULTORES Y EJECUTORES SRL.	20604008680	-	Ing. Andree Correa	Gerente	946881546	-	-
DANIEL RIOJAS	-	-	Daniel Riojas S.	Gerente	976751515	-	-
CONSORCIO O&C	20611033037	-	-	Gerente	-	-	-
PEDRO ANTONIO VIZARRETA VÁSQUEZ	10214972137	-	PEDRO ANTONIO VIZARRETA VÁSQUEZ	Gerente	945573859	-	-
CONSORCIO COREMARCA	20570866371	-	Villy Nuñez	Gerente	944976194	-	-
JARYAA SRL	20600908546	-	Daniel Martín Alcalde Galvez	Gerente	930752382	-	-
CONSORCIO VIRGEN DE LA PUERTA	20612105953	-	Edward Briones Rodríguez	Gerente	970556939	-	-
SOLETANCHE BACHY	20600373863	-	Yamilé Quispe	Gerente	937021115	-	-
HUAMANI PERU SAC	20555707950	-	Ing. Jhon	Gerente	948313607	-	-
CONCRETERA CAXAMARCA EIRL	20612155683	-	Ing. Royer Gómez	Gerente	976007412	-	-
CHINA GEZHOUBA GROUP COMPANY LIMITED SUCURSAL PERU	20602371442	-	Ing.Luis Dávila	Gerente	991568005	-	-
GRUPO CALLE	20604063630	-	Ing. Basilio Ávila	Gerente	991779456	-	-
JOSE LUIS RODRIGUEZ COBA	-	-	JOSE LUIS RODRIGUEZ COBA	Gerente	932959868	-	-
JARQ CONSULTORES & EJECUTORES EIRL	20608070860	-	Julio barboza	Gerente	954713825	-	-
NUBE BLANCA EIRL	20495648568	-	Administradora Karen Urrutia Bazán	Gerente	976598200	-	-
ADVANCED MANAGEMENT & CONSTRUCTION PROJECTS S.A.C	20611363002	-	Lennis Quezada C.	Gerente	957594686	-	-
JOSE LUIS IDROGO	10407011223	-	Carlos Mercado	Gerente	958795586	-	-
ACR CONSTRUCCIONES Y SERVICIOS	20604718041	-	Walter Bustamante	Gerente	940081051	-	-
ANDICO INGENIEROS SRL	20600824822	-	Vanesa Salazar Bacilio	Gerente	932395674	-	-
CONTROL DE POLVO TOTAL	20611172886	-	Ing. Ronny Tejada	Gerente	944222277	-	-
CONSORCIO SOGORÓN	20612884642	-	Consorcio Sogorón	Gerente	950416435	-	-
NÚCLEO EJECUTOR	-	-	Núcleo Ejecutor N.E. CONVENIO N° 1082-1309-2023-220-LLIB/VMVU/PNVR	Gerente	965890879	-	-
SIERRA INGENIERIA & CONSTRUCCIÓN	20608423690	-	Segundo Carranza Triaxiales Chiclayo Lab	Gerente	931137511	-	-
CONSORCIO DIM INGENIEROS	20612349089	-	ING. RAUL PLASENCIA	Gerente	-	-	-
CONSULTORA GAV SAC	20602111041	-	Ing. Bruno Banoni	Gerente	932006032	-	-
SANTA ROSA SERVICIOS GENERALES EIRL	20496092300	-	SANTA ROSA SERVICIOS GENERALES EIRL	Gerente	-	-	-
CONSORCIO LA QUINUA	20607155977	-	ING. ALEX YUPANQUI	Gerente	997483142	-	-
CATVAL	20612607886	-	CESAR MICHEL PAREDES ESTELA	Gerente	-	-	-
INGENIERIA GEODESIA TOPOGRAFIA Y CONTROL S.A.C.	20606140755	-	Ing. Cristian	Gerente	970202057	-	-
DISTRIBUIDORA & SERVICIOS GENERALES LIMACON EIRL	20609108631	-	Lennis Quezada C.	Gerente	957594686	-	-
CONSORCIO EDUCATIVO CAJAMARCA	20613143034	-	Ing. Gustavo Ramirez	Gerente	952965763	-	-
SERVICIOS GENERALES RECOZA EIRL	-	-	Lorena Terrones	Gerente	968830566	-	-
CEMOSA INGENIERIA Y CONTROL	20603980124	-	Mario Ortiz	Gerente	999046988	-	-
INKACRETE PERU	20604228795	-	Ivan Atalaya	Gerente	976729829	-	-
G&S Servicios de Ingeniería SRL	20453774318	-	Mardely Rosas	Gerente	940436925	-	-
M & T Mendoza y Tapia	20510949770	-	Ing. Gilmer Julca	Gerente	982763023	-	-
MACADAM	20601958644	-	Ing. Paola	Gerente	987110736	-	-
DEYFOR EIRL	20453830323	-	Cesar Marin	Gerente	955780075	-	-
CONSORCIO SUPERVISOR VICTORINO	20613459597	-	WALTER B.	Gerente	940081051	-	-
BEGAS INGENIEROS	20492246566	-	Limber Begas	Gerente	992280497	-	-
GROUP ROMERO GYM EIRL	20610550038	-	Ing.Gregorio	Gerente	926158529	-	-
CNOOD E&C S.A.C.	20606951699	-	Ing. Jean Pierre	Gerente	975655104	-	-
SERMUCAJ EIRL	20453754473	-	-	Gerente	963715775	-	-
ARACELY FLORES VASQUEZ	-	-	ARACELY FLORES VASQUEZ	Gerente	939684736	-	-
DISTRIBUIDORA NORTE PACASMAYO SRL	20131644524	-	Sherman Ascho Guzman	Gerente	93570867	-	-
ÁREA TÉCNICA DE LA UNIDAD ZONAL IV CAJAMARCA	20503503639	-	Ing. Gianina Isabel Vertiz Zamora	Gerente	-	-	-
MUNICIPALIDAD PROVINCIAL DE CAJAMARCA	20143623042	-	Ing. Pajares	Gerente	979023564	-	-
Servicio de consultoría y Estudios S.A.C. (SECOE SAC)	20602655807	-	Ing. Navarrete	Gerente	990789486	-	-
PROJECTS & COMMISSIONING CONSULTANTS S.A.C.	20600547306	-	NELSON HUATAY MACHUCA -GLORIA INFANTE	Gerente	986736117	-	-
DENIS JARA - TESISTA	-	-	DENIS JARA - TESISTA	Gerente	913042485	-	-
GCL INGENIERIA	20602488579	-	-	Gerente	-	-	-
PROYECTO ESPECIAL DE INFRAESTRUCTURA DE TRANSPORTE NACIONAL - PROVIAS NACIONAL	20503503639	-	-	Gerente	-	-	-
MANUEL VASQUEZ	-	-	-	Gerente	-	-	-
SAGITARIO ASOCIADOS	20517562158	-	Ing. Alexis Cornejo	Gerente	994894219	-	-
FAM. ROJAS	-	-	Ronal Rojas	Gerente	992337330	-	-
SOINTEL PERU SAC	20563485222	-	Ing. Roberto Asca	Gerente	973640672	-	-
LUIS OLANO TIRADO	42248297	-	Luis Olano	Gerente	923005670	-	-
SITES DEL PERÚ	20607207152	-	Ing. Eduardo Zapata	Gerente	914826551	-	-
JC THUNDER COMPANY	20610996001	-	Diana Llico	Gerente	997786469	-	-
ARQUITECNOLOGÍA	20609275252	-	Eliud Remugio Rubina	Gerente	901578364	-	-
SCALA PERÚ	20605252657	-	Fernando Espejo	Gerente	976933019	-	-
EDWIN ALEX CHÁVEZ GUTIERREZ	-	-	EDWIN ALEX CHÁVEZ GUTIERREZ	Gerente	926416431	-	-
James Cabanillas	10423343490	-	-	Gerente	925394688	-	-
AMC INGENIEROS S.A.C.	20296847829	-	Carmen Marley Sullon Quispe	Gerente	933206173	-	-
-	-	-	Oimer Fernandez Uriarte	Gerente	941764328	-	-
Jhonatan Florian	-	-	-	Gerente	973424263	-	-
CONSORCIO SUPERVISOR VIAL	20612954624	-	Carmen Marley Sullon Quispe	Gerente	-	-	-
KIAVACA	20604828865	-	-	Gerente	-	-	-
YOFC PERU S.A.C	20604175756	-	BUENO VALERA, JORGE RONALD	Gerente	959299242	-	-
ELY VASQUEZ	-	-	-	Gerente	-	-	-
CONSORCIO CAJAMARCA	20605252657	-	LISSETH GALLARDO	Gerente	940437064	-	-
CONSORCIO SUPERVISOR MOLLEPAMPA	20613539108	-	Ing. Cesar Augusto Marrufo	Gerente	962580167	-	-
Municipalidad Distrital de Quinua	20143629679	-	Rupert Limaco Avendaño	Gerente	922028870	-	-
CONSORCIO IST	20614321327	-	Raúl Plasencia	Gerente	910346280	-	-
CONSORCIO SAN MARTIN	20605119302	-	Ing. Airam Virgnia Briones Cabrera	Gerente	956419472	-	-
FKA CONSTRUCTORA E.I.R.L	20604519480	-	FRANCISCO J. KJURO AUCCA	Gerente	982276589	-	-
CERAMICOS CAJAMARCA SRL	20453661114	-	Benedicto Bobadilla Cortegana	Gerente	976949417	-	-
CONSORCIO PURHUAY	-	-	-	Gerente	-	-	-
Ing. Jenrry Chilon Villanueva	-	-	Jenrry Chilon Villanueva	Gerente	-	-	-
Concretera Ruiz	-	-	-	Gerente	-	-	-
B&M INGENIEROS Y ARQUITECTOS	20601739501	-	Ing. José Campos	Gerente	964872081	-	-
DAJUVE E.I.R.L	-	-	-	Gerente	-	-	-
ORGANISMO SUPERVISOR DE CONTRATACIONES DEL ESTADO	20419026809	-	Lizbeth Leiva Cisneros	Gerente	934079503	-	-
Cesar Paredes	-	-	Rossgri Paola Saldaña	Gerente	993459143	-	-
CONSORCIO VIAL HUAMACHUCO	20614226901	-	Smith Otimano Oliva	Gerente	912773105	-	-
INPROYEN CONSULTING SAC	20602643353	-	ALEXANDER COBEÑAS ACUÑA	Gerente	959792679	-	-
TESISTA	-	-	-	Gerente	-	-	-
CONSORCIO CAJAMARCA - NAMORA	-	-	-	Gerente	-	-	-
MUNICIPALIDAD PROVINCIAL DE SAN IGNACIO	-	-	-	Gerente	-	-	-
FREYA INGENIERIA Y CONSULTORIA INTEGRAL S.A.C.	22606672293	-	Gimena Mendoza Astete	Gerente	983104639	-	-
POWER CRUZ INGENIERIA	-	-	-	Gerente	-	-	-
COLLOTAN	-	-	-	Gerente	-	-	-
CONSORCIO CHAMIS - CORPORACIÓN ARLOC	-	-	-	Gerente	-	-	-
NUEVO SAN JOSÉ	-	-	-	Gerente	-	-	-
TEG&T TECNICOS ESPECIALISTAS EN GEOSINTETICOS Y TUBERIAS S.R.L.	-	-	Ing. Cristian Mantilla	Gerente	917337049	-	-
TELECONSTRUCTORES SAC	20492606015	-	Ing. Daniel A. Ramos Z.	Gerente	947697590	-	-
Susana - RENIEC	-	-	Arq Susana Guzmán Santos	Gerente	949250517	-	-
Luis Angel Lopez Pompa	-	-	Luis Angel Lopez Pompa	Gerente	910095559	-	-
ICHUS SERVICIOS GENERALES SAC	20495684874	-	Janeth	Gerente	976156531	-	-
SERVICIOS INNOVADORES CAXAMARCA S.A.C	20605098283	-	-	Gerente	-	-	-
COLEGIO MÉDICO DEL PERÚ	-	-	-	Gerente	-	-	-
CANTERA LOZANO	-	-	-	Gerente	-	-	-
ING. JULCAMORO	-	-	-	Gerente	-	-	-
ISAIAS ALFARO	-	-	-	Gerente	-	-	-
CONVIAL	-	-	-	Gerente	-	-	-
ING. WALTER TIRADO	-	-	-	Gerente	-	-	-
PAVIEMNTO DJ	-	-	-	Gerente	-	-	-
RILEVE Y INGENIERIA E.I.R.L	-	-	-	Gerente	-	-	-
SANTA ELENA	-	-	-	Gerente	-	-	-
OSCAR COTRINA	-	-	-	Gerente	-	-	-
SEDACAJ	-	-	-	Gerente	-	-	-
ING. JHONI VALDIVIA	-	-	-	Gerente	-	-	-
CONSORCIO PUEBLO NUEVO	-	-	-	Gerente	-	-	-
ECOSUL	-	-	-	Gerente	-	-	-
CHINA ROAD AND BRIDGE	-	-	-	Gerente	-	-	-
""".strip()


def clean_text(value):
    if value is None:
        return ""
    value = str(value).replace("\xa0", " ").strip()
    if value in {"-", "None", "none", "nan", "NaN"}:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def clean_phone(value):
    value = clean_text(value)
    if not value:
        return "-"
    value = re.sub(r"[^\d]", "", value)
    return value if value else "-"


def clean_ruc(value):
    value = clean_text(value)
    if not value:
        return ""
    value = re.sub(r"[^\d]", "", value)
    return value


def build_fake_email(name, index):
    base = clean_text(name).lower()
    if not base:
        base = f"cliente{index}"
    base = re.sub(r"[^\w\s]", "", base)
    base = re.sub(r"\s+", ".", base).strip(".")
    if not base:
        base = f"cliente{index}"
    return f"{base}@cliente.local"


def build_unique_sin_ruc():
    """
    Genera un identificador único de 11 chars para el campo ruc.
    Ejemplo: SINRUC00001
    """
    prefix = "SINRUC"
    last = (
        Cliente.objects
        .filter(ruc__startswith=prefix)
        .order_by("-ruc")
        .first()
    )

    if last and last.ruc:
        suffix = last.ruc[len(prefix):]
        try:
            next_num = int(suffix) + 1
        except ValueError:
            next_num = 1
    else:
        next_num = 1

    while True:
        candidate = f"{prefix}{next_num:05d}"  # 11 chars
        if not Cliente.objects.filter(ruc=candidate).exists():
            return candidate
        next_num += 1


def parse_data(raw_text):
    rows = []
    for i, line in enumerate(raw_text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 8:
            print(f"⚠ Línea {i} omitida: columnas insuficientes.")
            continue

        razon_social, ruc, direccion, persona_contacto, cargo, celular, web, correo = parts[:8]

        row = {
            "razon_social": clean_text(razon_social),
            "ruc": clean_ruc(ruc),
            "direccion": clean_text(direccion),
            "persona_contacto": clean_text(persona_contacto),
            "cargo_contacto": clean_text(cargo) or "Gerente",
            "celular_contacto": clean_phone(celular),
            "sitio_web": clean_text(web),
            "correo_contacto": clean_text(correo),
        }

        if not row["razon_social"]:
            print(f"⚠ Línea {i} omitida: razón social vacía.")
            continue

        rows.append(row)
    return rows


def upsert_cliente(row, index):
    razon_social = row["razon_social"]
    ruc_real = row["ruc"]

    defaults = {
        "razon_social": razon_social,
        "direccion": row["direccion"] or "",
        "sitio_web": row["sitio_web"] or "",
        "persona_contacto": row["persona_contacto"] or razon_social,
        "cargo_contacto": row["cargo_contacto"] or "Gerente",
        "celular_contacto": row["celular_contacto"] or "-",
        "correo_contacto": row["correo_contacto"] or build_fake_email(razon_social, index),
        "activo": True,
    }

    # Caso 1: tiene RUC real
    if ruc_real:
        existing = Cliente.objects.filter(ruc=ruc_real).first()
        if existing:
            return "duplicado_ruc", existing

        # si no existe, crear nuevo
        obj = Cliente.objects.create(ruc=ruc_real, **defaults)
        return "creado_ruc", obj

    # Caso 2: no tiene RUC real
    # Validar por razón social para no duplicar al volver a correr el script
    existing_by_name = Cliente.objects.filter(razon_social__iexact=razon_social).first()
    if existing_by_name:
        return "duplicado_nombre", existing_by_name

    fake_ruc = build_unique_sin_ruc()
    obj = Cliente.objects.create(ruc=fake_ruc, **defaults)
    return "creado_sin_ruc", obj


def main():
    rows = parse_data(DATA)

    creados_con_ruc = 0
    creados_sin_ruc = 0
    duplicados_ruc = 0
    duplicados_nombre = 0
    errores = 0

    print(f"📦 Registros detectados: {len(rows)}")
    print("-" * 70)

    for idx, row in enumerate(rows, start=1):
        try:
            estado, obj = upsert_cliente(row, idx)

            if estado == "creado_ruc":
                creados_con_ruc += 1
                print(f"✅ [RUC] {obj.ruc} | {obj.razon_social}")

            elif estado == "creado_sin_ruc":
                creados_sin_ruc += 1
                print(f"✅ [SIN RUC] {obj.ruc} | {obj.razon_social}")

            elif estado == "duplicado_ruc":
                duplicados_ruc += 1
                print(f"⏭ DUPLICADO RUC: {obj.ruc} | {obj.razon_social}")

            elif estado == "duplicado_nombre":
                duplicados_nombre += 1
                print(f"⏭ DUPLICADO NOMBRE: {obj.razon_social}")

        except Exception as e:
            errores += 1
            print(f"❌ Error con '{row.get('razon_social', 'SIN NOMBRE')}': {e}")

    print("\n" + "=" * 70)
    print("RESUMEN DE CARGA")
    print("=" * 70)
    print(f"✅ Creados con RUC real : {creados_con_ruc}")
    print(f"✅ Creados sin RUC      : {creados_sin_ruc}")
    print(f"⏭ Duplicados por RUC   : {duplicados_ruc}")
    print(f"⏭ Duplicados por nombre: {duplicados_nombre}")
    print(f"❌ Errores              : {errores}")
    print("=" * 70)


if __name__ == "__main__":
    main()