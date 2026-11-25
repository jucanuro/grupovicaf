# -*- coding: utf-8 -*-
"""
Fuente de verdad del catálogo de condiciones de la oferta técnico-económica
(VCF-LAB-FOR-001 **versión 07, 2026-11-05**, copiado del Word oficial):
`CatalogoCondicionSeccion` / `CatalogoCondicionItem`.

Lo resaltado en el Word:
  - Un dato a completar dentro del texto (XX, montos, calicatas) va entre
    `{{ }}`. El formulario de la cotización lo pinta en amarillo y el PDF lo
    imprime sin las llaves (`servicios/oferta_pdf.py`).
  - Un párrafo resaltado completo es una alternativa (formas de pago, validez,
    plazo, opiniones): va sin llaves y sin «D», salvo la opción de siempre.

Lo usan:
  - `cargar_condiciones.py` (raíz del repo): CLI con dry-run / --apply.
  - `python manage.py sembrar_demo`: lo siembra junto con el resto de catálogos.

`sembrar_condiciones()` es idempotente: `update_or_create` por `codigo` de
sección y por `(seccion, orden)` en los ítems, así que puede correrse varias
veces sin duplicar.

Convenciones de los flags por ítem:
  - Los textos con XX son plantillas que se completan al cotizar
    -> editable_en_cotizacion=True, seleccionado_por_defecto=False
  - Las condiciones generales van seleccionadas por defecto ("D")
  - Las condiciones específicas de un servicio (alquiler, campo, mina, EMS)
    NO van por defecto: se marcan según el servicio cotizado
  - "O" = obligatorio (siempre se incluye)
  - "-E" = no editable en cotización
"""

from django.db import transaction

from servicios.models import CatalogoCondicionSeccion, CatalogoCondicionItem

# Tipo de nodo de cada fila de `items`.
G = "grupo"
I = "item"
GRUPO = G
ITEM = I


ESTRUCTURA = [
    # ------------------------------------------------------------------
    {
        "codigo": "NOTAS",
        "titulo": "NOTAS:",
        "tipo": "notas",
        "orden": 1,
        "es_obligatoria": False,
        "items": [
            (I, 0, None, "(*) Los métodos indicados, se encuentran Acreditados por INACAL-DA.", {"D": True}),
            (I, 0, None, "Grupo VICAF SAC cuenta con la Certificación ISO 9001 para el alcance de “Servicios de Estudios de Mecánica de Suelos para proyectos de Construcción e Infraestructura”.", {}),
            (I, 0, None, "El Laboratorio no emitirá opiniones ni interpretaciones referentes a los resultados de los ensayos.", {"D": True}),
            (I, 0, None, "El Laboratorio realizará opiniones e interpretaciones de los resultados obtenidos en los ensayos; sin embargo, ésta actividad no se encuentra contemplada en el Alcance de Acreditación de INACAL", {}),
            (I, 0, None, "Los métodos indicados están referidos a la versión indicada de la norma, de requerir que se use una versión anterior y/o versiones retiradas el solicitante deberá indicarlo expresamente.", {"D": True}),
            (I, 0, None, "Las desviaciones a los métodos para cualquier actividad de laboratorio serán documentadas y comunicadas al Cliente, la ejecución procederá bajo autorización del Cliente. Son desviaciones comunes: muestra insuficiente, muestras contaminadas, muestras inalteradas (fisuradas, secas, etc.), entre otros.", {"D": True}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "PAGO",
        "titulo": "FORMAS DE PAGO y CONTRATACIÓN DEL SERVICIO",
        "tipo": "lista",
        "orden": 2,
        "es_obligatoria": True,
        "items": [
            (I, 0, 'Pago adelantado', "Forma de pago: Por adelantado.", {"D": True}),
            (I, 0, 'Pago 50/50', "Forma de pago: 50% por adelantado y 50% previo a la entrega del informe final.", {}),
            (I, 0, 'Pago 50/30/20', "Forma de pago: 50% por adelantado, 30% al finalizar el trabajo de campo y 20% previo a la entrega del informe final.", {}),
            (I, 0, 'Pago por valorizaciones', "Forma de pago: valorizaciones mensuales con pago a 07 días calendario de emitida la factura; la aprobación de las Valorizaciones tiene un plazo máximo de 05 días calendario luego de emitidas, de no darse respuesta se entenderá como aprobada sin observaciones y se estará emitiendo la factura para posterior pago.", {}),
            (I, 0, 'Pago posterior a la conformidad', "Forma de pago: posterior a la conformidad del servicio.", {}),
            (I, 0, 'Validez 15 días', "Plazo de validez de la oferta: 15 días calendario.", {}),
            (I, 0, 'Validez 30 días', "Plazo de validez de la oferta: 30 días calendario.", {"D": True}),
            (I, 0, None, "El comprobante del pago y de detracción (cuando aplique) deberá ser enviado al correo informes@grupovicaf.com", {"D": True, "O": True}),
            (I, 0, None, "Como aceptación de la oferta, favor de remitir Orden de Servicio o Contrato. Se considera como aceptación de la oferta, el ingreso de muestras al laboratorio o el envío de la Orden de Ensayos.", {"D": True, "O": True}),
            (I, 0, None, "Si realiza el pago en efectivo en otra localidad, se deberá incluir la comisión bancaria correspondiente que aplica el Banco de Crédito del Perú. De igual modo si realiza una transferencia interbancaria.", {"D": True}),
            (I, 0, None, "La facturación se realizará a la razón social que indique el cliente y en concordancia a los pagos realizados.", {"D": True}),
            (I, 0, None, "Modificación de informes: Toda modificación de un informe emitido que se origine en información errónea proporcionada por el cliente tendrá un costo adicional de S/ 10,00 por informe de ensayos y de S/ 30,00 por informe de consultoría, como estudios de mecánica de suelos (EMS) o diseños de mezclas.", {"D": True}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "PLAZO",
        "titulo": "DISPONIBILIDAD, PLAZO DE EJECUCIÓN DEL SERVICIO",
        "tipo": "lista",
        "orden": 3,
        "es_obligatoria": True,
        "items": [
            (I, 0, None, "El plazo de ejecución de los ensayos dependerá del tipo de muestra, condiciones iniciales de humedad, cantidad de muestra utilizable y la disponibilidad operativa de laboratorio GRUPO VICAF SAC.", {"D": True}),
            (I, 0, 'Plazo coordinado', "Plazo de entrega de resultados: Según la coordinación con el cliente.", {}),
            (I, 0, 'Plazo probetas (24 h)', "Plazo de entrega de resultados para ensayos en probetas: Los resultados se entregarán dentro de las 24 horas posteriores a la ejecución del ensayo. Los resultados de los ensayos realizados los sábados se entregarán el lunes siguiente.", {}),
            (I, 0, 'Plazo en días', "Plazo de entrega de resultados: {{XX días calendario}}.", {}),
            (I, 0, None, "El plazo de entrega de resultados será contabilizado a partir del cumplimiento de los siguientes requisitos: aceptación del servicio, pago según lo establecido y recepción de la orden de ensayos debidamente completada en el formato VCF-LAB-FOR-003, VCF-LAB-FOR-004, ingreso de las muestras de ensayo.", {"D": True}),
            (I, 0, None, "Confirmación del plazo: El plazo de entrega está sujeto a la fecha de inicio del servicio y a la disponibilidad de programación. Se recomienda confirmar dicho plazo al momento de aceptar la cotización.", {"D": True}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "CONDICIONES",
        "titulo": "CONDICIONES Y DETALLES DEL SERVICIO",
        "tipo": "lista",
        "orden": 4,
        "es_obligatoria": True,
        "items": [
            (I, 0, None, "El muestreo y la entrega de los ítems de ensayo son responsabilidades del cliente. Los ítems de ensayo deberán ser entregados en el laboratorio GRUPO VICAF SAC., ubicado en Jr. Los Topacios 440. Referencia: Cerca al complejo Qhapaq Ñan.", {"D": True, "O": True}),
            (I, 0, None, "El horario de recepción de las muestras es de Lunes a viernes 8:00 – 13:00 / 15:00 – 18:00 y sábado de 8:00 – 13:00. La entrega – recepción de muestras deberá ser coordinada con los responsables del laboratorio.", {"D": True, "O": True}),
            (G, 0, 'Ensayos en suelos, agregados, rocas y agua', "ENSAYOS EN SUELOS, AGREGADOS, ROCAS Y AGUA", {}),
            (I, 1, None, "Para que las muestras conserven las condiciones reales en las que fue muestreado, EL CLIENTE deberá utilizar bolsas herméticas adecuadas para cubrir y proteger la muestra, mismas que deberán protegerse del sol.", {}),
            (I, 1, None, "Cantidad de muestra requerida: {{XX}} kg.", {}),
            (I, 1, None, "El cliente deberá hacer llegar los datos de los ítems de ensayo en el formato: VCF-LAB-FOR-003 «Orden de Ensayos - Suelos, Agregados, Rocas y Agua», de no contar con dicha información, no se dará inicio al servicio.", {}),
            (G, 0, 'Ensayos en concreto', "ENSAYOS EN CONCRETO", {}),
            (I, 1, None, "Se recomienda que el traslado de las muestras sea posterior a las 8h del fraguado final. Durante su transporte, proteja las muestras con material de amortiguación adecuado para evitar daños por sacudidas, proteja las muestras con material aislante adecuado y evite la pérdida de humedad durante el transporte envolviendo las muestras en plástico o trapos húmedos. Procurar que el tiempo de transporte no exceda las 4 h. (ASTM C31 / C31M).", {}),
            (I, 1, None, "El cliente deberá hacer llegar los datos de los ítems de ensayo en el formato: VCF-LAB-FOR-004 ORDEN DE ENSAYOS - RESISTENCIA A LA COMPRESIÓN, de no contar con dicha información, no se dará inicio al servicio.", {}),
            (G, 0, 'Alquiler de equipos', "ALQUILER DE EQUIPOS", {}),
            (I, 1, None, "El cliente es responsable de la salida – entrada de los equipos en el laboratorio GRUPO VICAF SAC., ubicado en Jr. Los Topacios 440. Referencia: Cerca al complejo Qhapaq Ñan.", {}),
            (I, 1, None, "El horario de atención para recojo y entrega de equipos es de Lunes a viernes 9:00 – 13:00 / 15:00 – 18:00 y sábado de 9:00 – 13:00. La salida – entrada deberá ser coordinada con los contactos autorizados.", {}),
            (I, 1, None, "Los equipos serán entregados al cliente en óptimas condiciones de funcionamiento.", {}),
            (I, 1, None, "La persona responsable de recibir los equipos deberá firmar el documento VCF-LAB-FOR-067 COMPROMISO DE ALQUILER.", {}),
            (I, 1, None, "El cliente deberá proporcionar una garantía de S/ {{XXXX,00}}, monto que será devuelto por Grupo VICAF SAC una vez que se haya recibido el equipo alquilado y se verifique que se encuentra en óptimas condiciones.", {}),
            (I, 1, None, "Los equipos en alquiler deberán usarse con personal competente para su uso.", {}),
            (I, 1, None, "El cliente deberá garantizar la seguridad de los equipos en caso éstos se deban disponer en sus instalaciones o almacén de obra; el lugar de almacenamiento estará libre de goteras, descargas eléctricas, humo, luz solar directa u otro agente que pueda deteriorar los equipos u ocasionar que éstos se malogren.", {}),
            (I, 1, None, "GRUPO VICAF SAC. no será responsable de ningún daño o lesión causados por el uso incorrecto o negligente del Equipo por parte del Arrendatario, en caso suceda el arrendatario deberá pagar la suma de dinero que subsane los daños o cubran los gastos de reposición del equipo.", {}),
            (I, 1, None, "El Cliente deberá coordinar con anticipación si desea una ampliación de plazo de alquiler de los equipos.", {}),
            (I, 1, None, "Los moldes para la elaboración de probetas de concreto deberán recubrirse ligeramente con desmoldante antes de su uso y deberán ser devueltos sin restos de concreto.", {}),
            (G, 0, 'Ensayos en campo', "ENSAYOS EN CAMPO", {}),
            (G, 1, 'Densidad mediante el cono y la arena', "DENSIDAD MEDIANTE EL CONO Y LA ARENA", {}),
            (I, 2, None, "El cliente estará a cargo de indicar la ubicación del punto o puntos de ensayo.", {}),
            (I, 2, None, "El personal designado al servicio solo ejecutará ensayos de Densidad de Campo mediante la norma NTP 339.143 Revisada en 2019 y Contenido de Humedad mediante el uso de Humedómetro (Speedy).", {}),
            (I, 2, None, "El cliente deberá garantizar la seguridad de los equipos en caso éstos se deban disponer en sus instalaciones o almacén de obra; el lugar de almacenamiento estará libre de goteras, descargas eléctricas, humo, luz solar directa u otro agente que pueda deteriorar los equipos u ocasionar que éstos se malogren.", {}),
            (I, 2, None, "La propuesta no considera gastos por: trámite de Fotocheck ni EMO en el caso sea necesario. De requerirse estará a cargo del cliente.", {}),
            (I, 2, None, "La propuesta considera {{XX}} días para la movilización del técnico de Cajamarca – {{XX}}.", {}),
            (I, 2, None, "La propuesta considera {{XX}} días de trabajo de campo.", {}),
            (I, 2, None, "Rendimiento: Hasta 8 ensayos de densidad de campo por jornada de 8 horas. Una mayor cantidad deberá coordinarse con anticipación.", {}),
            (I, 2, None, "El costo del servicio incluye la movilidad desde Cajamarca hasta la zona del proyecto.", {}),
            (I, 2, None, "El cliente estará a cargo del traslado del personal y equipos desde Cajamarca hasta la ubicación de cada punto de ensayo y viceversa.", {}),
            (I, 2, None, "El cliente estará a cargo de la alimentación y hospedaje del personal; así como del resguardo de los equipos de laboratorio.", {}),
            (I, 2, None, "El cliente deberá coordinar con anticipación la disponibilidad del personal para la fecha y hora requeridas.", {}),
            (G, 1, 'Extracción de núcleos diamantinos', "EXTRACCIÓN DE NÚCLEOS DIAMANTINOS", {}),
            (I, 2, None, "El cliente estará a cargo de indicar la ubicación de los puntos de ensayo.", {}),
            (I, 2, None, "Grupo VICAF no se responsabiliza de la representatividad del ensayo para el área seleccionada o espesores de capa indicados, estos parámetros son definidos por el cliente.", {}),
            (I, 2, None, "El personal designado al servicio solo ejecutará los ensayos descritos en la presente oferta.", {}),
            (I, 2, None, "La propuesta no considera gastos por: trámite de Fotocheck ni EMO en el caso sea necesario. De requerirse estará a cargo del cliente.", {}),
            (I, 2, None, "La propuesta considera {{XX}} días para la movilización del técnico de Cajamarca – {{XX}}.", {}),
            (I, 2, None, "La propuesta considera {{XX}} días de trabajo de campo.", {}),
            (I, 2, None, "El costo del servicio incluye la movilidad desde Cajamarca hasta la zona del proyecto.", {}),
            (I, 2, None, "El cliente estará a cargo del traslado del personal y equipos desde Cajamarca hasta la ubicación de cada punto de ensayo y viceversa.", {}),
            (I, 2, None, "El cliente estará a cargo de la alimentación del personal.", {}),
            (I, 2, None, "El cliente deberá coordinar con anticipación la disponibilidad del personal para la fecha y hora requeridas.", {}),
            (G, 0, 'Trabajos en mina', "TRABAJOS EN MINA", {}),
            (I, 1, None, "La presente oferta no considera gastos de tiempos de inducción, de requerirse estos serán asumidos por el cliente, considerando tiempo del personal (S/ 150.00 por día) y el pago por los cursos requeridos.", {}),
            (I, 1, None, "El trámite de fotocheck estará a cargo del cliente.", {}),
            (I, 1, None, "El traslado del personal y equipos estará a cargo del cliente, considerando como punto de partida y retorno Jr. Los Topacios 440 – Cajamarca.", {}),
            (I, 1, None, "El trámite logístico para ingreso de equipos a la Unidad Minera estará a cargo del cliente.", {}),
            (G, 0, 'Estudio de mecánica de suelos', "ESTUDIO DE MECÁNICA DE SUELOS", {}),
            (I, 1, None, "Según la Norma E.050, se recomienda un mínimo de 03 calicatas; sin embargo, por solicitud del cliente, la presente cotización considera solo {{01 calicata 02 calicatas}}, dejando constancia de que el cliente comprende las limitaciones de representatividad de la información obtenida y la posible necesidad de complementar el estudio.", {}),
            (I, 1, None, "La norma E.050 Suelos y Cimentaciones, 2018, en el artículo 12 OBLIGACIONES DEL SOLICITANTE, menciona que es obligación del solicitante proporcionar la información indicada en el artículo 13 y garantizar el libre acceso al terreno para efectuar la exploración de campo.", {}),
            (I, 1, None, "El CLIENTE se encargará de los permisos para el ingreso al terreno del proyecto, el cual debe encontrarse libre (completamente desocupado en la zona de trabajo) para poder efectuar la exploración de campo y de ser el caso, contar con las autorizaciones respectivas de la entidad competente para efectuar el trabajo de exploración de campo.", {}),
            (I, 1, None, "El cliente deberá asignar a una persona como encargado para las coordinaciones necesarias en los días que dure el trabajo de campo; así mismo, el cliente brindará el contacto de este.", {}),
            (I, 1, None, "La cantidad de exploraciones y ensayos han sido determinadas por el cliente.", {}),
            (I, 1, None, "Para la determinación de la capacidad portante se realizará el ensayo de corte directo a solicitud del cliente.", {}),
            (I, 1, None, "De acuerdo con lo indicado en la norma E.050 de Suelos y Cimentaciones, se considera el ensayo triaxial para el cálculo de la capacidad portante.", {}),
            (I, 1, None, "La propuesta no considera reposición de falso piso o cualquier obra de concreto.", {}),
            (I, 1, None, "Las calicatas serán tapadas al finalizar los trabajos de exploración, para lo cual no se considera un control de compactación.", {}),
            (I, 1, None, "De encontrarse estrato rocoso en la excavación, se detendrán los trabajos y se deberán considerar otros ensayos para la roca encontrada, esto será comunicado al cliente. (El desarrollo de estos ensayos no está considerado en el costo ni el plazo de esta oferta económica).", {}),
            (I, 1, None, "No se incluyen ensayos de Expansión, Colapso y SPT, de requerirse luego del análisis del presente estudio, los ensayos deberán cotizarse por separado. (El desarrollo de estos ensayos no está considerado en el costo ni en el plazo de esta oferta económica)", {}),
            (I, 1, None, "La cotización considera el programa mínimo de exploración, en el caso de que los suelos presenten condiciones especiales el programa deberá ser ampliado según el capítulo VI Problemas Especiales de Cimentación, esto será informado al cliente.", {}),
            (I, 1, None, "Grupo VICAF SAC, NO se responsabiliza por los plazos incumplidos, debido a razones ajenas al consultor, hechos fortuitos y/o de fuerza mayor.", {}),
            (G, 0, 'Otros', "OTROS", {"D": True}),
            (I, 1, None, "Otros procesos y/o métodos no indicados deberán ser cotizados en forma independiente", {"D": True}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "IMPARCIALIDAD",
        "titulo": "CONDICIONES DE IMPARCIALIDAD, CONFIDENCIALIDAD Y COMPETENCIA TÉCNICA",
        "tipo": "lista",
        "orden": 5,
        "es_obligatoria": True,
        "items": [
            (I, 0, None, "Grupo VICAF SAC, no cede ante presiones financieras, comerciales o de cualquier tipo que comprometan su imparcialidad frente a los resultados obtenidos.", {"D": True}),
            (I, 0, None, "Todo el personal de Grupo VICAF SAC, labora bajo políticas de imparcialidad y confidencialidad.", {"D": True, "O": True}),
            (I, 0, None, "El consultor es responsable de la información obtenida durante la ejecución del servicio, en caso el cliente considere que se ha incumplido con el compromiso de confidencialidad e imparcialidad, tiene la potestad de denunciar este hecho ante las instancias legales, que considere pertinentes.", {"D": True, "O": True}),
            (I, 0, None, "El cliente puede presentar sus quejas en el formulario: https://forms.gle/JM6oAugvSwyGPAKZ8 o escribirnos al correo quejas.reportes@grupovicaf.com donde también podrá reportar incidentes que afecten al Sistema de Gestión Antisoborno.", {"D": True, "O": True}),
            (I, 0, None, "El Laboratorio usará fotos del servicio como material para marketing, sin evidenciar resultados, ni nombre del cliente.", {"D": True}),
            (I, 0, None, "El Laboratorio informará al cliente, con antelación la información adicional que pretenda poner al alcance del público; excepto por la información que el cliente pone a disposición del público, o cuando lo acuerdan el laboratorio y el cliente (por ejemplo, con el propósito de responder a las quejas), cualquier otra información se considera información del cliente y se considera confidencial.", {"D": True}),
            (I, 0, None, "Cuando el laboratorio sea requerido por ley o autorizado por las disposiciones contractuales, para revelar información confidencial, se notificará al cliente o a la persona interesada la información proporcionada, salvo que esté prohibido por ley.", {"D": True}),
            (I, 0, None, "La información acerca del cliente, obtenida de fuentes diferentes del cliente (por ejemplo, quejas o información de organismos reglamentarios), se considera confidencial entre el cliente y el laboratorio. La fuente de esta información se mantendrá como confidencial por parte del laboratorio y no se compartirá con el cliente, a menos que se acuerde lo contrario con la fuente.", {"D": True}),
            (I, 0, None, "Grupo VICAF SAC cuenta con la capacidad técnica para la realización de la consultoría. Frente a situaciones inesperadas, el servicio podrá ser subcontratado previa coordinación con el cliente.", {"D": True}),
            (I, 0, None, "El Informe Técnico final, será entregado al responsable designado por el cliente.", {"D": True}),
            (I, 0, None, "Se garantiza la imparcialidad y confidencialidad de los resultados proporcionados al cliente.", {"D": True, "O": True}),
        ],
    },
]

# Secciones de versiones anteriores que ya no van en el catálogo: contactos y
# datos de pago son fijos en la plantilla del PDF; «Otros» es un grupo de CONDICIONES.
CODIGOS_RETIRADOS = ["OTROS", "CONTACTOS", "DATOS_PAGO"]


def otras_secciones_activas():
    """Secciones activas del catálogo que no vienen del Word (creadas a mano)."""
    codigos = [b["codigo"] for b in ESTRUCTURA]
    return CatalogoCondicionSeccion.objects.filter(activo=True).exclude(codigo__in=codigos)


def sembrar_condiciones(solo_word=False):
    """Crea o actualiza todo el catálogo de condiciones. Idempotente.

    No imprime nada; devuelve ``(n_secciones, n_items)``. Todo corre dentro de
    una transacción. Con ``solo_word`` también desactiva las secciones creadas
    a mano que no están en el Word (se pueden reactivar en el admin).
    """
    total_sec = total_item = 0

    with transaction.atomic():
        for bloque in ESTRUCTURA:
            seccion, _ = CatalogoCondicionSeccion.objects.update_or_create(
                codigo=bloque["codigo"],
                defaults={
                    "titulo": bloque["titulo"],
                    "tipo": bloque["tipo"],
                    "orden": bloque["orden"],
                    "activo": True,
                    "es_obligatoria": bloque["es_obligatoria"],
                },
            )
            total_sec += 1

            # padres por nivel, para reconstruir la jerarquía de ítems
            padres = {}
            orden = 0

            for tipo_nodo, nivel, titulo, texto, flags in bloque["items"]:
                orden += 1
                parent = padres.get(nivel - 1) if nivel > 0 else None

                obj, _ = CatalogoCondicionItem.objects.update_or_create(
                    seccion=seccion,
                    orden=orden,
                    defaults={
                        "tipo_nodo": tipo_nodo,
                        "titulo": titulo,
                        "texto": texto,
                        "nivel": nivel,
                        "parent": parent,
                        "activo": True,
                        "seleccionado_por_defecto": flags.get("D", False),
                        "es_obligatorio": flags.get("O", False),
                        "editable_en_cotizacion": not flags.get("-E", False),
                    },
                )
                total_item += 1
                if tipo_nodo == G:
                    padres[nivel] = obj

            # Lo que sobra de una versión anterior queda inactivo (no se borra:
            # las cotizaciones guardan su copia, pero el vínculo se conserva).
            seccion.items.filter(orden__gt=orden).update(activo=False)

        CatalogoCondicionSeccion.objects.filter(codigo__in=CODIGOS_RETIRADOS).update(activo=False)
        if solo_word:
            otras_secciones_activas().update(activo=False)

    return total_sec, total_item


def iter_preview():
    """Genera líneas de texto describiendo el catálogo, sin tocar la BD.

    Lo usa `cargar_condiciones.py` para el dry-run.
    """
    for bloque in ESTRUCTURA:
        yield "\n" + "=" * 70
        yield f"SECCIÓN {bloque['orden']}. {bloque['titulo']}  [{bloque['codigo']}]"
        yield "=" * 70
        for tipo_nodo, nivel, titulo, texto, flags in bloque["items"]:
            marca = "G" if tipo_nodo == G else " "
            check = "*" if flags.get("D", False) else " "
            sangria = "  " * nivel
            yield f"  [{marca}{check}] {sangria}{(titulo or texto)[:70]}"
