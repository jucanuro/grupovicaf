# VCF-WEB · Requirements · Asistente de WhatsApp

| Módulo | Fuente | Versión | Fecha | Estado |
|---|---|---|---|---|
| VCF-WEB | `docs/proc/VCF-WEB_HU_CU_v1.md` v1.4 (G1 aprobado por el Gerente) · D-VCF-004 | v1 | 2026-10-15 | Aprobado por el Gerente (modo rápido) |

Alcance: opción A de DP-WEB-01. Es un widget guiado que termina en `wa.me` con el mensaje armado y queda preparado para pasar a C (leads). HU-WEB-05 queda **fuera de alcance**.

## Requisitos (EARS)

| ID | Requisito | HU / CA |
|---|---|---|
| REQ-WEB-01 | EL SISTEMA DEBE mostrar el botón flotante de WhatsApp en todas las páginas públicas de la web (una sola vez por página). | HU-WEB-01 · CA-01.5 |
| REQ-WEB-02 | SI `NegocioConfig.whatsapp` está vacío, ENTONCES EL SISTEMA NO DEBE mostrar el botón ni el asistente. | HU-WEB-04 · CA-04.4 |
| REQ-WEB-03 | SI el navegador no ejecuta JavaScript, ENTONCES EL SISTEMA DEBE mantener el botón como enlace `https://wa.me/<solo dígitos>`. | HU-WEB-01 · CA-01.3 |
| REQ-WEB-04 | CUANDO el visitante haga clic en el botón, EL SISTEMA DEBE abrir el panel con el saludo T-01 y el menú T-02 (servicios, cotización, asesor). | HU-WEB-01 · CA-01.1 |
| REQ-WEB-05 | EL SISTEMA DEBE elegir el saludo según la hora de America/Lima: "Buenos días" de 05:00 a 11:59, "Buenas tardes" de 12:00 a 18:59 y "Buenas noches" de 19:00 a 04:59. | HU-WEB-01 · CA-01.6, RN-10 |
| REQ-WEB-06 | CUANDO el visitante cierre el panel o pulse Esc, EL SISTEMA DEBE ocultarlo, mantener el botón visible y devolverle el foco. | HU-WEB-01 · CA-01.2, CA-01.4 |
| REQ-WEB-07 | CUANDO el visitante elija "Ver nuestros servicios", EL SISTEMA DEBE listar las `LineaServicio` activas en su orden, y al elegir una, sus `ServicioPublicado` activos con título público y resumen. | HU-WEB-02 · CA-02.1, CA-02.2 |
| REQ-WEB-08 | CUANDO el visitante elija un ensayo, EL SISTEMA DEBE ofrecer "Ver página del servicio", "Solicitar una cotización" y "Consultar por WhatsApp". | HU-WEB-02 · CA-02.3, CA-02.4 |
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

Nota REQ-WEB-13: P-03 sigue abierta y la ubicación se pide como texto libre, así que con texto libre no se puede verificar del todo que una ubicación esté "dentro de Cajamarca". Se valida solo contra la lista de D-VCF-002, y el mensaje final agrega ", Cajamarca".

## Fuera de alcance
- HU-WEB-05 (guardar leads, opción C). El JS deja todas las respuestas en un solo objeto para que agregarlo luego sea un `fetch`.
- Configurar los mensajes de WhatsApp Business (T-50 y T-51): se hace a mano en la app.
