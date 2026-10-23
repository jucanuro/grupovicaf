# VCF-WEB · Requirements · Asistente de WhatsApp y certificado ISO 9001

| Módulo | Fuente | Versión | Fecha | Estado |
|---|---|---|---|---|
| VCF-WEB | `docs/proc/VCF-WEB_HU_CU_v1.md` v1.6 (G1 + cambio de alcance v1.5 + requerimiento nuevo v1.6 [Decisión Gerente]) · D-VCF-004 | v3 | 2026-10-23 | Aprobado por el Gerente (modo rápido) |

Alcance: opción A de DP-WEB-01. Es un widget guiado que termina en `wa.me` con el mensaje armado y queda preparado para pasar a C (leads). HU-WEB-05 queda **fuera de alcance**.

## Requisitos (EARS)

| ID | Requisito | HU / CA |
|---|---|---|
| REQ-WEB-01 | EL SISTEMA DEBE mostrar el botón flotante de WhatsApp en todas las páginas públicas de la web (una sola vez por página). | HU-WEB-01 · CA-01.5 |
| REQ-WEB-02 | SI `NegocioConfig.whatsapp` está vacío, ENTONCES EL SISTEMA NO DEBE mostrar el botón ni el asistente. | HU-WEB-04 · CA-04.4 |
| REQ-WEB-03 | SI el navegador no ejecuta JavaScript, ENTONCES EL SISTEMA DEBE mantener el botón como enlace `https://wa.me/<solo dígitos>`. | HU-WEB-01 · CA-01.3 |
| REQ-WEB-04 | CUANDO el visitante haga clic en el botón, EL SISTEMA DEBE abrir el panel con el saludo T-01 y el menú T-02 (servicios, cotización, asesor); si en la sesión ya hubo una conversación, DEBE retomar el último paso (REQ-WEB-23). *(v2)* | HU-WEB-01, HU-WEB-07 · CA-01.1, CA-07.5 |
| REQ-WEB-05 | EL SISTEMA DEBE elegir el saludo según la hora de America/Lima: "Buenos días" de 05:00 a 11:59, "Buenas tardes" de 12:00 a 18:59 y "Buenas noches" de 19:00 a 04:59. | HU-WEB-01 · CA-01.6, RN-10 |
| REQ-WEB-06 | CUANDO el visitante cierre el panel o pulse Esc, EL SISTEMA DEBE ocultarlo, mantener el botón visible y devolverle el foco. | HU-WEB-01 · CA-01.2, CA-01.4 |
| REQ-WEB-07 | CUANDO el visitante elija "Ver nuestros servicios", EL SISTEMA DEBE listar las `LineaServicio` activas en su orden, y al elegir una, sus `ServicioPublicado` activos con título público y resumen. | HU-WEB-02 · CA-02.1, CA-02.2 |
| REQ-WEB-08 | CUANDO el visitante elija un ensayo, EL SISTEMA DEBE ofrecer "Ver en la web" (REQ-WEB-20), "Consultar por WhatsApp" y "Sí, cotizar". *(v2: antes "Ver página del servicio")* | HU-WEB-02 · CA-02.3, CA-02.4 |
| REQ-WEB-09 | SI una línea no tiene ensayos publicados, ENTONCES EL SISTEMA DEBE mostrar T-13 y la opción de consultar por WhatsApp. | HU-WEB-02 · CA-02.6 |
| REQ-WEB-10 | EL SISTEMA NO DEBE exponer en el asistente ni en su endpoint precios, códigos de facturación, la marca de acreditado ni datos de clientes. | HU-WEB-02 · CA-02.5, RN-04 |
| REQ-WEB-11 | CUANDO el visitante elija "Solicitar una cotización", EL SISTEMA DEBE pedir uno por uno nombre, empresa (opcional, «Omitir»), servicio (lista + "Otro / no estoy seguro"), cantidad de muestras y ubicación en Cajamarca. | HU-WEB-03 · CA-03.1, CA-03.2, CA-03.5 |
| REQ-WEB-12 | SI la cantidad no es un entero entre 1 y 999, o el nombre, el servicio o la ubicación están vacíos, ENTONCES EL SISTEMA DEBE mostrar el aviso y no avanzar. | HU-WEB-03 · CA-03.3, CA-03.4 |
| REQ-WEB-13 | SI la ubicación nombra una provincia excluida por D-VCF-002, ENTONCES EL SISTEMA DEBE mostrar T-25e y pedirla de nuevo. | HU-WEB-03 · CA-03.6 (parcial, ver nota) |
| REQ-WEB-14 | MIENTRAS el visitante esté respondiendo, EL SISTEMA DEBE permitirle volver al paso anterior sin perder lo escrito. | HU-WEB-03 · CA-03.7 |
| REQ-WEB-15 | CUANDO el visitante complete los datos, EL SISTEMA DEBE mostrar el resumen T-26 con las opciones "Enviar por WhatsApp" y "Corregir". | HU-WEB-03 · CA-03.8 |
| REQ-WEB-16 | CUANDO el visitante confirme, EL SISTEMA DEBE abrir en una pestaña nueva `https://wa.me/<dígitos>?text=<mensaje>`, con el mensaje de la sección 7.5 codificado para URL e iniciado con el saludo. | HU-WEB-04 · CA-04.1, CA-04.2, CA-04.3, CA-01.7 |
| REQ-WEB-17 | CUANDO el visitante elija "Conversar con un asesor", EL SISTEMA DEBE mostrar T-30 y un botón que abra WhatsApp con el mensaje de asesor. | HU-WEB-06 · CA-06.1 |
| REQ-WEB-18 | CUANDO el asistente vaya a abrir WhatsApp fuera del horario (L-V 8:00-13:00 y 15:00-18:00, sáb 8:00-13:00, hora de Lima), EL SISTEMA DEBE mostrar antes T-40 con el horario de `NegocioConfig`. | HU-WEB-04, HU-WEB-06 · CA-04.5, CA-06.2 |
| REQ-WEB-19 | EL SISTEMA DEBE leer el número de WhatsApp y el horario de `NegocioConfig`, nunca escritos en plantillas o JS. | RN-03 |

### v2 · Cambio de alcance [Decisión Gerente] (2026-10-23)

| ID | Requisito | HU / CA |
|---|---|---|
| REQ-WEB-20 | CUANDO el asistente muestre el detalle de una línea (T-11 o T-13) o de un ensayo (T-12), EL SISTEMA DEBE ofrecer el enlace "Ver en la web" a su página en `/servicios/<slug>/`, que se abre en la misma pestaña. | HU-WEB-02 · CA-02.3 |
| REQ-WEB-21 | SI la línea o el ensayo no tiene página publicada (inactivo, o su slug lo resuelve otra página), ENTONCES EL SISTEMA NO DEBE mostrar "Ver en la web" y el endpoint DEBE enviar `url: null`. | HU-WEB-02 · CA-02.7, RN-14 |
| REQ-WEB-22 | MIENTRAS el panel esté abierto, CUANDO el visitante cargue otra página de la web, EL SISTEMA DEBE mostrar el panel abierto en el mismo paso, con las respuestas dadas, sin mover el foco ni el desplazamiento de la página. | HU-WEB-07 · CA-07.1 |
| REQ-WEB-23 | EL SISTEMA DEBE guardar el paso, las respuestas y si el panel está abierto en `sessionStorage` del navegador, y nunca enviarlos al servidor. | HU-WEB-07 · CA-07.1, CA-07.5, RN-12 |
| REQ-WEB-24 | SI el paso guardado ya no existe en el catálogo (línea o ensayo despublicado), ENTONCES EL SISTEMA DEBE mostrar el paso válido más cercano (lista de líneas o menú). | HU-WEB-07 · CU-WEB-03 4a |
| REQ-WEB-25 | MIENTRAS el panel muestre un paso distinto del menú, EL SISTEMA DEBE mostrar en la cabecera el botón "Menú principal", que lleva a T-01 con Servicios / Cotización / Asesor. | HU-WEB-07 · CA-07.2 |
| REQ-WEB-26 | CUANDO el visitante elija "Sí, cotizar" en el detalle de un ensayo, también tras navegar, EL SISTEMA DEBE iniciar la cotización con ese servicio ya elegido y saltar la pregunta de servicio. | HU-WEB-07 · CA-07.3 |
| REQ-WEB-27 | CUANDO el visitante cierre el panel (× o Esc), EL SISTEMA DEBE guardar que está cerrado y NO DEBE abrirlo por su cuenta en esa página ni en las siguientes de la sesión. | HU-WEB-07 · CA-07.4, RN-13 |
| REQ-WEB-28 | DONDE el ancho de pantalla sea menor de 640 px, EL SISTEMA DEBE mostrar el panel a lo ancho con márgenes de 16 px, con el área de mensajes limitada a 40 % del alto de la pantalla, sin capa que bloquee la página, ocultar el botón flotante mientras el panel está abierto y reservar al final de la página el alto del panel para que todo el contenido se pueda leer por encima. | HU-WEB-07 · CA-07.6 |
| REQ-WEB-29 | SI `sessionStorage` no está disponible, ENTONCES EL SISTEMA DEBE funcionar como en v1 (sin restaurar entre páginas) y sin errores. | HU-WEB-07 · CA-07.7 |

Nota REQ-WEB-13: P-03 sigue abierta y la ubicación se pide como texto libre, así que con texto libre no se puede verificar del todo que una ubicación esté "dentro de Cajamarca". Se valida solo contra la lista de D-VCF-002, y el mensaje final agrega ", Cajamarca".

### v3 · Certificado ISO 9001 [Decisión Gerente] (2026-10-23)

| ID | Requisito | HU / CA |
|---|---|---|
| REQ-WEB-30 | MIENTRAS exista una `Certificacion` publicada (activa, con PDF y `vigencia_hasta` ≥ fecha de Lima), EL SISTEMA DEBE mostrar en `/acreditacion/`, después de las acreditaciones INACAL, una tarjeta con el sello (o el distintivo de texto con la norma si no hay sello), la norma, el sistema de gestión, el N.º de certificado, el organismo certificador, el alcance, la sede, la fecha de emisión y la de vencimiento, y el botón "Ver certificado". | HU-WEB-08 · CA-08.1, RN-15 |
| REQ-WEB-31 | SI la certificación está inactiva, no tiene PDF o su `vigencia_hasta` es anterior a la fecha de Lima, ENTONCES EL SISTEMA NO DEBE mostrar su tarjeta, ni el modal del visor, ni declararla en el JSON-LD. | HU-WEB-08 · CA-08.5, RN-15 |
| REQ-WEB-32 | CUANDO el visitante pulse "Ver certificado" y el navegador tenga pantalla de 768 px o más, puntero fino con hover y visor de PDF (`navigator.pdfViewerEnabled` distinto de `false`), EL SISTEMA DEBE abrir un modal con el PDF embebido en un `<iframe>` y los botones "Descargar" (descarga el mismo PDF) y "Cerrar". El PDF se carga al abrir, no con la página. | HU-WEB-08 · CA-08.2 |
| REQ-WEB-33 | CUANDO el modal esté abierto y el visitante pulse Esc, haga clic en el fondo, o pulse "Cerrar" o ×, EL SISTEMA DEBE cerrarlo, liberar el PDF y devolver el foco al botón que lo abrió. | HU-WEB-08 · CA-08.3 |
| REQ-WEB-34 | MIENTRAS el modal esté abierto, EL SISTEMA DEBE tener `role="dialog"`, `aria-modal="true"` y `aria-labelledby` con el título, poner el foco en el primer control, hacer que Tab y Shift+Tab ciclen solo entre los controles del modal y bloquear el desplazamiento de la página. | HU-WEB-08 · CA-08.3 |
| REQ-WEB-35 | DONDE no se cumplan las condiciones de REQ-WEB-32, o el navegador no ejecute JavaScript, EL SISTEMA DEBE abrir el PDF en una pestaña nueva (`<a target="_blank" rel="noopener">`) y no mostrar el modal. | HU-WEB-08 · CA-08.4 |
| REQ-WEB-36 | EL SISTEMA DEBE permitir crear y editar certificaciones en el admin de `laboratorio.grupovicaf.com` con: norma, sistema de gestión, N.º, organismo, alcance, sede, fecha de emisión, fecha de vigencia (obligatoria), PDF (`FileField`, solo PDF con firma `%PDF-`, máximo 10 MB), sello (`ImageField`, opcional) con texto alternativo obligatorio si hay sello, orden y activo. | HU-WEB-08 · CA-08.6 |
| REQ-WEB-37 | EL SISTEMA DEBE servir los PDF de `/media/certificaciones/` con `X-Frame-Options: SAMEORIGIN` (en dev y en nginx) para que la propia web los pueda embeber, y mantener `DENY` en el resto de respuestas. | HU-WEB-08 · CA-08.2 |
| REQ-WEB-38 | MIENTRAS haya certificaciones publicadas, EL SISTEMA DEBE declararlas en el JSON-LD `LocalBusiness` global como `hasCertification` (tipo `Certification`: `name`, `certificationIdentification`, `issuedBy`, `validFrom`, `expires`, `certificationStatus`, `url` del PDF), sin tocar el `hasCredential` de INACAL. | HU-WEB-08 · CA-08.7 |

## Fuera de alcance
- Enlaces "Ver en la web" dentro de las listas de líneas y de ensayos: cada fila ya lleva a su detalle, y ahí está el enlace (REQ-WEB-20).
- HU-WEB-05 (guardar leads, opción C). El JS deja todas las respuestas en un solo objeto para que agregarlo luego sea un `fetch`.
- Configurar los mensajes de WhatsApp Business (T-50 y T-51): se hace a mano en la app.
- *(v3)* Mostrar el certificado ISO 9001 en la home o en el footer: el requerimiento lo pide solo en /acreditacion/.
- *(v3)* Visor PDF propio (pdf.js): se usa el visor del navegador; en móvil, la pestaña nueva.
- *(v3)* Ocultar el archivo PDF vencido de `/media/`: la tarjeta desaparece, pero la URL directa sigue respondiendo mientras el archivo exista. Para retirarlo, el administrador borra el archivo desde el admin.
