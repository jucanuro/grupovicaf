# -*- coding: utf-8 -*-
"""
Fuente de verdad del catálogo de condiciones de la oferta técnico-económica
(VCF-LAB-FOR-001): `CatalogoCondicionSeccion` / `CatalogoCondicionItem`.

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
        "titulo": "Notas",
        "tipo": "notas",
        "orden": 1,
        "es_obligatoria": True,
        "items": [
            (I, 0, None, "(*) Los métodos indicados, se encuentran Acreditados por INACAL-DA.", {"D": True}),
            (I, 0, None, "El Laboratorio no emitirá opiniones ni interpretaciones referentes a los resultados de los ensayos.", {"D": True}),
            (I, 0, None, "El Laboratorio realizará opiniones e interpretaciones de los resultados obtenidos en los ensayos; sin embargo, ésta actividad no se encuentra contemplada en el Alcance.", {}),
            (I, 0, None, "Los métodos indicados están referidos a la versión indicada de la norma, de requerir que se use una versión anterior y/o versiones retiradas el solicitante deberá indicarlo expresamente.", {"D": True}),
            (I, 0, None, "Las desviaciones a los métodos para cualquier actividad de laboratorio serán documentadas y comunicadas al Cliente, la ejecución procederá bajo autorización del Cliente. Son desviaciones comunes: muestra insuficiente, muestras contaminadas, muestras inalteradas (fisuradas, secas, etc.), entre otros.", {"D": True}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "PAGO",
        "titulo": "Formas de pago y contratación del servicio",
        "tipo": "lista",
        "orden": 2,
        "es_obligatoria": True,
        "items": [
            # Las tres formas de pago son excluyentes: se elige una al cotizar
            (I, 0, "Pago adelantado", "Forma de pago: Por adelantado.", {}),
            (I, 0, "Pago parcial", "Forma de pago: XX% por adelantado y XX% previo a la entrega del informe final.", {}),
            (I, 0, "Pago por valorizaciones", "Forma de pago: posterior a la conformidad del servicio, mediante valorizaciones.", {}),
            (I, 0, "Validez", "Plazo de validez de la oferta: XX días calendario.", {"D": True}),
            (I, 0, None, "El comprobante del pago y de detracción (cuando aplique) deberá ser enviado al correo informes@grupovicaf.com", {"D": True, "O": True}),
            (I, 0, None, "Como aceptación de la oferta, favor de remitir Orden de Servicio, Contrato o la presente oferta firmada.", {"D": True, "O": True}),
            (I, 0, None, "Si realiza el pago en efectivo en otra localidad, se deberá incluir la comisión bancaria correspondiente que aplica el Banco de Crédito del Perú. De igual modo si realiza una transferencia interbancaria.", {"D": True}),
            (I, 0, None, "La facturación se realizará a la razón social que indique el cliente y en concordancia a los pagos realizados.", {"D": True}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "PLAZO",
        "titulo": "Disponibilidad y plazo de ejecución del servicio",
        "tipo": "lista",
        "orden": 3,
        "es_obligatoria": True,
        "items": [
            (I, 0, None, "El plazo de ejecución de los ensayos dependerá del tipo de muestra, condiciones iniciales de humedad, cantidad de muestra utilizable y la disponibilidad operativa del laboratorio GRUPO VICAF SAC.", {"D": True}),
            (I, 0, None, "El plazo de ejecución del servicio iniciará al día siguiente de realizada la entrega de muestras, aceptación de la Oferta y realizado el pago de acuerdo con las condiciones establecidas.", {"D": True}),
            (I, 0, "Plazo coordinado", "Plazo de entrega de resultados: según la coordinación con el cliente.", {}),
            (I, 0, "Plazo en días", "Plazo de entrega de resultados: XX días calendario, contados a partir de la aceptación del servicio y pago del adelanto.", {}),
            (I, 0, "Probetas 24 h", "Para probetas de 24 h se deben considerar los fines de semana.", {}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "CONDICIONES",
        "titulo": "Condiciones y detalles del servicio",
        "tipo": "lista",
        "orden": 4,
        "es_obligatoria": True,
        "items": [
            # --- Condiciones generales de recepción ---
            (I, 0, None, "El muestreo y la entrega de los ítems de ensayo son responsabilidades del cliente. Los ítems de ensayo deberán ser entregados en el laboratorio GRUPO VICAF SAC., ubicado en Jr. Los Topacios 440. Referencia: cerca al complejo Qhapaq Ñan.", {"D": True, "O": True}),
            (I, 0, None, "El horario de recepción de las muestras es de lunes a viernes 8:00 – 13:00 / 15:00 – 18:00 y sábado de 8:00 – 13:00. La entrega y recepción de muestras deberá ser coordinada con los responsables del laboratorio.", {"D": True, "O": True}),

            # --- Grupo: suelos, agregados, rocas y agua ---
            (G, 0, "Suelos, agregados, rocas y agua", "ENSAYOS EN SUELOS, AGREGADOS, ROCAS Y AGUA", {}),
            (I, 1, None, "Para que las muestras conserven las condiciones reales en las que fue muestreado, EL CLIENTE deberá utilizar bolsas herméticas adecuadas para cubrir y proteger la muestra, mismas que deberán protegerse del sol.", {}),
            (I, 1, None, "La cantidad de muestra suficiente para cada ensayo se deberá tener en cuenta en base al documento XX. Cantidad de muestra requerida.", {}),
            (I, 1, None, "El cliente deberá hacer llegar los datos de los ítems de ensayo en el formato VCF-LAB-FOR-003 ORDEN DE ENSAYOS - SUELOS, AGREGADOS, ROCAS Y AGUA; de no contar con dicha información, no se dará inicio al servicio.", {}),

            # --- Grupo: concreto ---
            (G, 0, "Concreto", "ENSAYOS EN CONCRETO", {}),
            (I, 1, None, "Para la codificación de las muestras se recomienda tener en cuenta lo señalado en el documento XX.", {}),
            (I, 1, None, "Se recomienda que el traslado de las muestras sea posterior a las 8 h del fraguado final. Durante su transporte, proteja las muestras con material de amortiguación adecuado para evitar daños por sacudidas, proteja las muestras con material aislante adecuado y evite la pérdida de humedad envolviéndolas en plástico o trapos húmedos. Procurar que el tiempo de transporte no exceda las 4 h (ASTM C31 / C31M).", {}),
            (I, 1, None, "El cliente deberá hacer llegar los datos de los ítems de ensayo en el formato VCF-LAB-FOR-004 ORDEN DE ENSAYOS - RESISTENCIA A LA COMPRESIÓN; de no contar con dicha información, no se dará inicio al servicio.", {}),

            # --- Grupo: alquiler de equipos ---
            (G, 0, "Alquiler de equipos", "ALQUILER DE EQUIPOS", {}),
            (I, 1, None, "El cliente es responsable de la salida y entrada de los equipos en el laboratorio GRUPO VICAF SAC., ubicado en Jr. Los Topacios 440. Referencia: cerca al complejo Qhapaq Ñan.", {}),
            (I, 1, None, "El horario de atención para recojo y entrega de equipos es de lunes a viernes 9:00 – 13:00 / 15:00 – 18:00 y sábado de 9:00 – 13:00. La salida y entrada deberá ser coordinada con los contactos autorizados.", {}),
            (I, 1, None, "Los equipos serán entregados al cliente en óptimas condiciones de funcionamiento.", {}),
            (I, 1, None, "La persona responsable de recibir los equipos deberá firmar el documento VCF-LAB-FOR-067 COMPROMISO DE ALQUILER.", {}),
            (I, 1, None, "El cliente deberá proporcionar una garantía de S/ XXXX,00, monto que será devuelto por Grupo VICAF SAC una vez recibido el equipo alquilado y verificado que se encuentra en óptimas condiciones.", {}),
            (I, 1, None, "Los equipos en alquiler deberán usarse con personal competente para su uso.", {}),
            (I, 1, None, "El cliente deberá garantizar la seguridad de los equipos en caso éstos se deban disponer en sus instalaciones o almacén de obra; el lugar de almacenamiento estará libre de goteras, descargas eléctricas, humo, luz solar directa u otro agente que pueda deteriorar los equipos u ocasionar que éstos se malogren.", {}),
            (I, 1, None, "GRUPO VICAF SAC. no será responsable de ningún daño o lesión causados por el uso incorrecto o negligente del equipo por parte del arrendatario; en caso suceda, el arrendatario deberá pagar la suma de dinero que subsane los daños o cubra los gastos de reposición del equipo.", {}),
            (I, 1, None, "El cliente deberá coordinar con anticipación si desea una ampliación de plazo de alquiler de los equipos.", {}),
            (I, 1, None, "Los moldes para la elaboración de probetas de concreto deberán recubrirse ligeramente con aceite o desmoldante antes de su uso y deberán ser devueltos sin restos de concreto.", {}),

            # --- Grupo: ensayos en campo ---
            (G, 0, "Ensayos en campo", "ENSAYOS EN CAMPO", {}),

            (G, 1, "Densidad cono y arena", "DENSIDAD MEDIANTE EL CONO Y LA ARENA", {}),
            (I, 2, None, "El cliente estará a cargo de indicar la ubicación del punto o puntos de ensayo.", {}),
            (I, 2, None, "El personal designado al servicio solo ejecutará ensayos de Densidad de Campo mediante la norma NTP 339.143 revisada en 2019 y Contenido de Humedad mediante el uso de humedómetro (Speedy).", {}),
            (I, 2, None, "El cliente deberá garantizar la seguridad de los equipos en caso éstos se deban disponer en sus instalaciones o almacén de obra; el lugar de almacenamiento estará libre de goteras, descargas eléctricas, humo, luz solar directa u otro agente que pueda deteriorar los equipos.", {}),
            (I, 2, None, "La propuesta no considera gastos por trámite de fotocheck ni EMO en caso sea necesario. De requerirse, estará a cargo del cliente.", {}),
            (I, 2, None, "La propuesta considera XX días para la movilización del técnico de Cajamarca – XX.", {}),
            (I, 2, None, "La propuesta considera XX días de trabajo de campo.", {}),
            (I, 2, "Rendimiento", "RENDIMIENTO", {}),
            (I, 2, None, "El cliente estará a cargo del traslado del personal y equipos desde Cajamarca hasta la ubicación de cada punto de ensayo y viceversa.", {}),
            (I, 2, None, "El cliente estará a cargo de la alimentación y hospedaje del personal, así como del resguardo de los equipos de laboratorio.", {}),
            (I, 2, None, "El cliente deberá realizar las coordinaciones correspondientes con la anticipación pertinente.", {}),
            (I, 2, None, "El costo del servicio incluye la movilidad desde Cajamarca hasta la zona del proyecto.", {}),

            (G, 1, "Núcleos diamantinos", "EXTRACCIÓN DE NÚCLEOS DIAMANTINOS", {}),
            (I, 2, None, "El cliente estará a cargo de indicar la ubicación del punto o puntos de ensayo.", {}),
            (I, 2, None, "El personal designado al servicio solo ejecutará los ensayos descritos en la presente oferta.", {}),
            (I, 2, None, "La propuesta no considera gastos por trámite de fotocheck ni EMO en caso sea necesario. De requerirse, estará a cargo del cliente.", {}),
            (I, 2, None, "La propuesta considera XX días para la movilización del técnico de Cajamarca – XX.", {}),
            (I, 2, None, "La propuesta considera XX días de trabajo de campo.", {}),
            (I, 2, None, "El cliente estará a cargo del traslado del personal y equipos desde Cajamarca hasta la ubicación de cada punto de ensayo y viceversa.", {}),
            (I, 2, None, "El cliente estará a cargo de la alimentación del personal.", {}),
            (I, 2, None, "El cliente deberá realizar las coordinaciones correspondientes con la anticipación pertinente.", {}),
            (I, 2, None, "El costo del servicio incluye la movilidad desde Cajamarca hasta la zona del proyecto.", {}),

            (G, 1, "Trabajos en mina", "TRABAJOS EN MINA", {}),
            (I, 2, None, "La presente oferta no considera gastos de tiempos de inducción; de requerirse, éstos serán asumidos por el cliente, considerando tiempo del personal (S/ 150.00 por día) y el pago por los cursos requeridos.", {}),
            (I, 2, None, "El trámite de fotocheck estará a cargo del cliente.", {}),
            (I, 2, None, "El traslado del personal y equipos estará a cargo del cliente, considerando como punto de partida y retorno Jr. Los Topacios 440 – Cajamarca.", {}),

            # --- Grupo: estudio de mecánica de suelos ---
            (G, 0, "Estudio de mecánica de suelos", "ESTUDIO DE MECÁNICA DE SUELOS", {}),
            (I, 1, None, "La norma E.050 Suelos y Cimentaciones (2018), en su artículo 12 OBLIGACIONES DEL SOLICITANTE, menciona que es obligación del solicitante proporcionar la información indicada en el artículo 13 y garantizar el libre acceso al terreno para efectuar la exploración de campo.", {}),
            (I, 1, None, "El CLIENTE se encargará de los permisos para el ingreso al terreno del proyecto, el cual debe encontrarse libre (completamente desocupado en la zona de trabajo) para poder efectuar la exploración de campo y, de ser el caso, contar con las autorizaciones respectivas de la entidad competente.", {}),
            (I, 1, None, "El cliente deberá asignar a una persona como encargado para las coordinaciones necesarias en los días que dure el trabajo de campo; asimismo, el cliente brindará el contacto de ésta.", {}),
            (I, 1, None, "La cantidad de exploraciones y ensayos ha sido determinada por el cliente.", {}),
            (I, 1, None, "Para la determinación de la capacidad portante se realizará el ensayo de corte directo a solicitud del cliente.", {}),
            (I, 1, None, "De acuerdo con lo indicado en la norma E.050 de Suelos y Cimentaciones, se considera el ensayo triaxial para el cálculo de la capacidad portante.", {}),
            (I, 1, None, "La propuesta no considera reposición de falso piso ni cualquier obra de concreto.", {}),
            (I, 1, None, "Las calicatas serán tapadas al finalizar los trabajos de exploración, para lo cual no se considera un control de compactación.", {}),
            (I, 1, None, "De encontrarse estrato rocoso en la excavación, se detendrán los trabajos y se deberán considerar otros ensayos para la roca encontrada; esto será comunicado al cliente. El desarrollo de estos ensayos no está considerado en el costo ni en el plazo de esta oferta económica.", {}),
            (I, 1, None, "No se incluyen ensayos de Expansión, Colapso y SPT; de requerirse luego del análisis del presente estudio, deberán cotizarse por separado. El desarrollo de estos ensayos no está considerado en el costo ni en el plazo de esta oferta económica.", {}),
            (I, 1, None, "La cotización considera el programa mínimo de exploración. En caso de que los suelos presenten condiciones especiales, el programa deberá ser ampliado según el capítulo VI Problemas Especiales de Cimentación; esto será informado al cliente.", {}),
            (I, 1, None, "Grupo VICAF SAC no se responsabiliza por los plazos incumplidos debido a razones ajenas al consultor, hechos fortuitos y/o de fuerza mayor.", {}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "OTROS",
        "titulo": "Otros",
        "tipo": "lista",
        "orden": 5,
        "es_obligatoria": False,
        "items": [
            (I, 0, None, "Otros procesos y/o métodos no indicados deberán ser cotizados en forma independiente.", {"D": True}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "IMPARCIALIDAD",
        "titulo": "Condiciones de imparcialidad, confidencialidad y competencia técnica",
        "tipo": "lista",
        "orden": 6,
        "es_obligatoria": True,
        "items": [
            (I, 0, None, "Grupo VICAF SAC no cede ante presiones financieras, comerciales o de cualquier tipo que comprometan su imparcialidad frente a los resultados obtenidos.", {"D": True, "O": True}),
            (I, 0, None, "Todo el personal de Grupo VICAF SAC labora bajo políticas de imparcialidad y confidencialidad.", {"D": True, "O": True}),
            (I, 0, None, "El consultor es responsable de la información obtenida durante la ejecución del servicio. En caso el cliente considere que se ha incumplido con el compromiso de confidencialidad e imparcialidad, tiene la potestad de denunciar este hecho ante las instancias legales que considere pertinentes.", {"D": True, "O": True}),
            (I, 0, None, "El cliente puede presentar sus quejas en el formulario https://forms.gle/JM6oAugvSwyGPAKZ8 o escribirnos al correo quejas.reportes@grupovicaf.com, donde también podrá reportar incidentes que afecten al Sistema de Gestión Antisoborno.", {"D": True, "O": True}),
            (I, 0, None, "El Laboratorio usará fotos del servicio como material para marketing, sin evidenciar resultados ni nombre del cliente.", {"D": True}),
            (I, 0, None, "El Laboratorio informará al cliente con antelación la información adicional que pretenda poner al alcance del público; excepto por la información que el cliente pone a disposición del público o cuando lo acuerdan el laboratorio y el cliente (por ejemplo, con el propósito de responder a quejas), cualquier otra información se considera información del cliente y se considera confidencial.", {"D": True}),
            (I, 0, None, "Cuando el laboratorio sea requerido por ley o autorizado por las disposiciones contractuales para revelar información confidencial, se notificará al cliente o a la persona interesada la información proporcionada, salvo que esté prohibido por ley.", {"D": True}),
            (I, 0, None, "La información acerca del cliente obtenida de fuentes diferentes del cliente (por ejemplo, quejas o información de organismos reglamentarios) se considera confidencial entre el cliente y el laboratorio. La fuente de esta información se mantendrá como confidencial por parte del laboratorio y no se compartirá con el cliente, a menos que se acuerde lo contrario con la fuente.", {"D": True}),
            (I, 0, None, "Grupo VICAF SAC cuenta con la capacidad técnica para la realización de la consultoría. Frente a situaciones inesperadas, el servicio podrá ser subcontratado previa coordinación con el cliente.", {"D": True}),
            (I, 0, None, "El Informe Técnico final será entregado al responsable designado por el cliente.", {"D": True}),
            (I, 0, None, "Se garantiza la imparcialidad y confidencialidad de los resultados proporcionados al cliente.", {"D": True, "O": True}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "CONTACTOS",
        "titulo": "Contactos autorizados del laboratorio",
        "tipo": "lista",
        "orden": 7,
        "es_obligatoria": True,
        "items": [
            (I, 0, None, "Todas las coordinaciones referidas al servicio serán válidas solo si se realizan con los contactos autorizados.", {"D": True, "O": True}),
        ],
    },
    # ------------------------------------------------------------------
    {
        "codigo": "DATOS_PAGO",
        "titulo": "Datos para contrato, orden de servicio y pagos",
        "tipo": "lista",
        "orden": 8,
        "es_obligatoria": True,
        "items": [
            (I, 0, "Razón social", "Razón Social: GRUPO VICAF SAC", {"D": True, "O": True, "-E": True}),
            (I, 0, "RUC", "RUC: 20609464632", {"D": True, "O": True, "-E": True}),
            (I, 0, "Dirección", "Dirección: Jr. Los Topacios 440 – Cajamarca", {"D": True, "O": True, "-E": True}),
            (I, 0, "Cuenta BCP", "Cuenta BCP (Soles): 24574415288082", {"D": True, "O": True, "-E": True}),
            (I, 0, "CCI", "Cuenta interbancaria (Soles): 00224517441528808291", {"D": True, "O": True, "-E": True}),
            (I, 0, "Detracción", "Cuenta de Detracción (BN): 00761271644", {"D": True, "O": True, "-E": True}),
        ],
    },
]


def sembrar_condiciones():
    """Crea o actualiza todo el catálogo de condiciones. Idempotente.

    No imprime nada; devuelve ``(n_secciones, n_items)``. Todo corre dentro de
    una transacción.
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
