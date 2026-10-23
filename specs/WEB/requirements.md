# VCF-WEB · Requirements · Asistente de WhatsApp y certificaciones

| Módulo | Fuente | Versión | Fecha | Estado |
|---|---|---|---|---|
| VCF-WEB | `docs/proc/VCF-WEB_HU_CU_v1.md` v1.8 (G1 + cambio de alcance v1.5 + requerimiento nuevo v1.6 + cambio de alcance v1.7 + cambio de diseño v1.8 [Decisión Gerente]) · D-VCF-002 · D-VCF-004 | v5 | 2026-10-23 | Aprobado por el Gerente (modo rápido) |

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

> **v4:** REQ-WEB-30 a 36 y 38 quedan **reemplazados** por REQ-WEB-39 a 52. REQ-WEB-37 (SAMEORIGIN en `/media/certificaciones/`) sigue vigente.

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

### v4 · Modelo único de certificaciones [Decisión Gerente] (2026-10-23)

| ID | Requisito | HU / CA |
|---|---|---|
| REQ-WEB-39 | EL SISTEMA DEBE tener un solo modelo `Certificacion` con título, descripción corta (≤ 200 caracteres), tipo (`acreditacion` "Acreditación", `iso` "Certificación ISO", `otro` "Otro"), institución que la otorga, archivo, fecha de vigencia opcional, orden y activo, editable desde el admin de `laboratorio.grupovicaf.com`. | HU-WEB-08 · CA-08.10 |
| REQ-WEB-40 | EL SISTEMA DEBE aceptar como archivo solo PDF (firma `%PDF-`) o imagen JPG, PNG o WebP que Pillow pueda abrir, de 10 MB como máximo, y rechazar lo demás con un aviso en el admin. | HU-WEB-08 · CA-08.10 |
| REQ-WEB-41 | CUANDO se apliquen las migraciones, EL SISTEMA DEBE pasar el certificado ISO 9001 existente al modelo nuevo (conservando su archivo, institución y vigencia) y crear la acreditación INACAL LE-230 con la imagen del certificado que hoy muestra la web y vigencia 2027-05-27, sin duplicarla si ya existe. | HU-WEB-08 · §2.5 |
| REQ-WEB-42 | EL SISTEMA DEBE publicar una certificación solo si está activa, tiene archivo y su vigencia está vacía o es ≥ la fecha de Lima, en las cards, el modal y el JSON-LD. | HU-WEB-08 · CA-08.7, RN-15 |
| REQ-WEB-43 | MIENTRAS haya certificaciones publicadas, EL SISTEMA DEBE mostrar en `/acreditacion/`, justo debajo del hero, una grilla de cards en el orden del admin con 1 columna por debajo de 640 px, 2 desde 640 px y 4 desde 1024 px. | HU-WEB-08 · CA-08.1 |
| REQ-WEB-44 | EL SISTEMA DEBE mostrar en cada card el tipo como etiqueta, el título (H3), la descripción corta y la institución, con el mismo alto para las cards de una fila y sin imagen del certificado. Toda la card es clicable mediante un único enlace (`<a href>` al archivo, `target="_blank"`), operable con teclado y con foco visible. | HU-WEB-08 · CA-08.2 |
| REQ-WEB-45 | CUANDO el visitante abra una card cuyo archivo sea imagen, EL SISTEMA DEBE mostrarla en el modal en cualquier dispositivo; la imagen se carga al abrir, no con la página. | HU-WEB-08 · CA-08.3 |
| REQ-WEB-46 | CUANDO el visitante abra una card cuyo archivo sea PDF y el navegador tenga pantalla de 768 px o más, puntero fino con hover y visor de PDF (`navigator.pdfViewerEnabled` distinto de `false`), EL SISTEMA DEBE mostrar el PDF embebido en un `<iframe>` del modal. DONDE no se cumplan esas condiciones, o no haya JavaScript, EL SISTEMA DEBE abrir el archivo en una pestaña nueva y no mostrar el modal. | HU-WEB-08 · CA-08.4 |
| REQ-WEB-47 | MIENTRAS el modal esté abierto, EL SISTEMA DEBE mostrar el título, "Descargar" (`<a download>` al mismo archivo) y "Cerrar"; CUANDO el visitante pulse Esc, haga clic en el fondo o pulse "Cerrar" o ×, EL SISTEMA DEBE cerrarlo, liberar el archivo y devolver el foco a la card. | HU-WEB-08 · CA-08.5 |
| REQ-WEB-48 | MIENTRAS el modal esté abierto, EL SISTEMA DEBE tener `role="dialog"`, `aria-modal="true"` y `aria-labelledby` con el título, poner el foco en ×, hacer que Tab y Shift+Tab ciclen solo entre los controles del modal y bloquear el desplazamiento de la página. | HU-WEB-08 · CA-08.6 |
| REQ-WEB-49 | MIENTRAS haya certificaciones publicadas, EL SISTEMA DEBE mostrar en la home una sección con las mismas cards (como máximo 4, en el orden del admin) y el enlace "Ver todas" a `/acreditacion/`, y NO DEBE mostrar la imagen grande del certificado. | HU-WEB-08 · CA-08.8, CA-08.9 |
| REQ-WEB-50 | CUANDO el visitante pulse los accesos "Ver certificado" de INACAL de la home o del hero de `/acreditacion/`, EL SISTEMA DEBE abrir el mismo modal con la primera certificación publicada de tipo Acreditación; SI no hay ninguna, ENTONCES el acceso DEBE llevar a `/acreditacion/`. | HU-WEB-08 · P-18 |
| REQ-WEB-51 | MIENTRAS haya certificaciones publicadas de tipo `iso` u `otro`, EL SISTEMA DEBE declararlas en `LocalBusiness.hasCertification` (tipo `Certification`: `name`, `description`, `issuedBy`, `expires` si hay vigencia, `certificationStatus`, `url` absoluta del archivo), sin tocar el `hasCredential` de INACAL. | HU-WEB-08 · CA-08.11 |
| REQ-WEB-52 | EL SISTEMA NO DEBE mostrar "norte del Perú" en la home ni en `/acreditacion/` (H1, meta, incluida la `NegocioConfig.descripcion` que usa la home, y textos): el ámbito es Cajamarca. | HU-WEB-08 · CA-08.12, D-VCF-002 |

### v5 · Todo en cards: ensayos acreditados [Decisión Gerente] (2026-10-23)

> La home ya cumple "todo en cards" desde v4 (servicios y certificaciones, REQ-WEB-49). v5 cambia la última lista de `/acreditacion/`: la sección de `Acreditacion` (alcance y ensayos acreditados), que P-16 mantuvo aparte.

| ID | Requisito | HU / CA |
|---|---|---|
| REQ-WEB-53 | MIENTRAS haya ensayos vinculados a una `Acreditacion` activa, EL SISTEMA DEBE mostrar en `/acreditacion/`, después de la grilla de certificaciones, la sección "Ensayos acreditados" (H2) con el alcance de cada acreditación y los ensayos como cards agrupadas por línea (H3 por línea, en el orden del admin), en una grilla de 1 columna por debajo de 640 px, 2 desde 640 px y 4 desde 1024 px. EL SISTEMA NO DEBE mostrar los ensayos como lista de viñetas. | HU-WEB-09 · CA-09.1 |
| REQ-WEB-54 | EL SISTEMA DEBE ubicar cada ensayo en un solo grupo: la primera `LineaServicio` activa (por `orden`, `nombre`) cuyo M2M `ensayos` lo incluye; si ninguna, la `linea` activa de su `ServicioPublicado`; si tampoco, el grupo "Otros ensayos acreditados", al final. Un ensayo vinculado a varias acreditaciones se muestra una vez; dentro de cada grupo, por nombre. | HU-WEB-09 · CA-09.2, P-19 |
| REQ-WEB-55 | EL SISTEMA DEBE mostrar en cada card del ensayo el nombre (H4; el título público si tiene ficha publicada), el código de la norma y la línea, con el mismo alto en cada fila. Toda la card es clicable con un único control (botón, o enlace a la ficha si existe), operable con teclado y con foco visible. | HU-WEB-09 · CA-09.3 |
| REQ-WEB-56 | CUANDO el visitante escriba en el buscador, EL SISTEMA DEBE mostrar solo las cards cuyo nombre, norma, método o línea contengan todas las palabras escritas, sin distinguir mayúsculas ni tildes; ocultar los grupos sin cards visibles y anunciar en una región `aria-live="polite"` cuántos ensayos se muestran. | HU-WEB-09 · CA-09.4 |
| REQ-WEB-57 | CUANDO el visitante pulse una línea en el filtro (botones "Todas" y uno por línea con ensayos, con `aria-pressed`), EL SISTEMA DEBE mostrar solo esa línea, combinada con el texto del buscador; "Todas" quita el filtro. | HU-WEB-09 · CA-09.5 |
| REQ-WEB-58 | SI el buscador y el filtro no dejan ninguna card, ENTONCES EL SISTEMA DEBE mostrar "No encontramos ensayos acreditados con ese criterio." y el botón "Limpiar búsqueda", que vacía el buscador y vuelve a "Todas". | HU-WEB-09 · CA-09.6 |
| REQ-WEB-59 | CUANDO el visitante abra una card de ensayo, EL SISTEMA DEBE abrir un modal (`role="dialog"`, `aria-modal="true"`, `aria-labelledby` con el nombre) con línea, norma (código y nombre), método, acreditación (institución y N.º) y, si tiene ficha publicada, su resumen y "Ver ficha del ensayo"; y siempre "Solicitar cotización" (`/contacto/cotizacion/`) y "Cerrar". El modal se comporta como en REQ-WEB-47 y 48: foco en ×, Tab y Shift+Tab atrapados, scroll bloqueado y cierre con Esc, fondo, × o "Cerrar" devolviendo el foco a la card. | HU-WEB-09 · CA-09.7, CA-09.8 |
| REQ-WEB-60 | EL SISTEMA NO DEBE incluir en el HTML de `/acreditacion/` (cards, modal ni JSON de datos) precio, unidad, código de facturación ni `esta_acreditado` de `servicios.Servicio`; la vista arma los datos con lista blanca. | HU-WEB-09 · CA-09.9, RN-16 |
| REQ-WEB-61 | DONDE el navegador no ejecute JavaScript, EL SISTEMA DEBE mostrar todas las cards con su información y sin buscador ni filtro (ocultos con `hidden` hasta que el JS los active); las cards con ficha publicada DEBEN ser un enlace a `/servicios/<slug>/`. "Ficha publicada" = `ServicioPublicado` activo cuyo slug no lo resuelve antes una línea activa (RN-14). | HU-WEB-09 · CA-09.10 |

## Fuera de alcance
- Enlaces "Ver en la web" dentro de las listas de líneas y de ensayos: cada fila ya lleva a su detalle, y ahí está el enlace (REQ-WEB-20).
- HU-WEB-05 (guardar leads, opción C). El JS deja todas las respuestas en un solo objeto para que agregarlo luego sea un `fetch`.
- Configurar los mensajes de WhatsApp Business (T-50 y T-51): se hace a mano en la app.
- ~~*(v3)* Mostrar el certificado ISO 9001 en la home o en el footer~~: *(v4)* la home sí muestra las cards (REQ-WEB-49). El footer sigue fuera de alcance.
- *(v3)* Visor PDF propio (pdf.js): se usa el visor del navegador; en móvil, la pestaña nueva.
- *(v4)* Fusionar `Acreditacion` (alcance y ensayos acreditados) con `Certificacion`: se mantiene aparte (P-16, cerrada en v1.8).
- *(v5)* Guardar en la URL o en el navegador lo buscado y la línea elegida: el filtro empieza vacío en cada visita.
- *(v5)* Precargar el ensayo en el formulario de `/contacto/cotizacion/` desde "Solicitar cotización": el enlace lleva al formulario vacío.
- *(v5)* Mostrar un ensayo en todas sus líneas (P-19).
- *(v4)* Corregir "norte del Perú" en `clientes.html` (PM-11).
- *(v3)* Ocultar el archivo PDF vencido de `/media/`: la tarjeta desaparece, pero la URL directa sigue respondiendo mientras el archivo exista. Para retirarlo, el administrador borra el archivo desde el admin.
