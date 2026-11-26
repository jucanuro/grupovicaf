# VCF-LIMS — Tasks

| Dueño | Versión | Fecha | Estado |
|---|---|---|---|
| DLF | v1 | 2026-11-03 | Terminado |

> Depende de `design.md` v1. Cada tarea cubre al menos un REQ y se verifica antes de marcarla `[x]`.

**Formato de commit:** `VCF-LIMS T<n>: <qué>`.

| T | Tarea | REQ | Verificación | Estado |
|---|---|---|---|---|
| T1 | Spec SDD del dashboard (requirements, design, tasks) | todos | Revisión del Gerente (G1 dado el 2026-11-03) | [x] |
| T2 | `core/dashboard.py` con periodo, KPI, series y agregaciones + pruebas unitarias | 01-03, 06, 11, 13-17, 21, 25 | `python manage.py test core` | [x] |
| T3 | Transiciones Enviada/Rechazada de la cotización (vistas, URLs, botones) + pruebas | 22-24 | `python manage.py test servicios` | [x] |
| T4 | Chart.js 4.4.1 en `static/vendor/` y `static/js/dashboard.js` | 06, 09, 14, 19 | Prueba unitaria del HTML + revisión visual | [x] |
| T5 | Nueva `templates/dashboard.html` (filtro, KPI, comercial, laboratorio, proyectos, tablas, vacíos, responsive) | 01-20 | E2E | [x] |
| T6 | `sembrar_e2e` con cotizaciones, solicitudes vencidas y proyectos + `e2e/dashboard.spec.js` | 01-08, 10-18, 20, 22-24 | `npm run test:e2e` | [x] |
| T7 | Spec de Análisis (requirements 27-40, design 5b, tasks) | 27-40 | G1 del Gerente (2026-11-03) | [x] |
| T8 | App `analisis`: `VistaAnalisis`, permiso `reportes.ver`, conjuntos Cotizaciones/Ítems/Clientes, vistas JSON + pruebas | 27, 29-31, 34, 35, 38-40 | `python manage.py test analisis` | [x] |
| T9 | Librerías en `static/vendor/`, `analisis.html`, `analisis.js`, `analisis.css` y accesos en los menús | 27, 28, 32, 33, 36, 37 | Revisión visual (escritorio y 390 px) | [x] |
| T10 | `sembrar_e2e` (febrero 2001, usuario `e2e.analista`) + `e2e/analisis.spec.js` | 27-30, 32-38 | `npm run test:e2e` | [x] |
| T11 | PR 2: conjuntos Muestras, Solicitudes, Ensayos asignados, Incidencias, Informes, Proyectos, Actividades y Bandeja web (cliente en Ensayos solo con `ensayos.ver_todos`) | 27, 29, 38, 39 | `python manage.py test analisis` + `e2e/analisis.spec.js` | [x] |
| T12 | Nueva presentación de Análisis: menú de conjuntos, zonas para arrastrar o tocar, números por tipo, frase y totales, preguntas frecuentes; sin jQuery ni PivotTable.js | 41, 42, 43 | `python manage.py test analisis` + `node --test tests/js/analisis-motor.test.js` + `e2e/analisis.spec.js` | [x] |
| T64 | `proyectos/avance.py` (RN-09 a 11), panel en tarjetas y filtro `?proyecto=` en recepciones, solicitudes e informes + pruebas | 44-52 | `python manage.py test proyectos.test_avance` | [x] |
| T65 | `sembrar_e2e` (P-E2E-AVANCE, usuario `e2e.jefe`) + `e2e/panel-proyectos.spec.js` | 44-47, 51 | `npm run test:e2e` | [x] |
| T66 | `cotizaciones_form.html` (pasos en pills, estado vacío, modal del detalle) y `cotizacion-config.js` (abrir/cerrar modal, «Editar» por fila) sin tocar la lógica del detalle | 53-59 | Revisión visual (escritorio y 390 px) | [x] |
| T67 | `sembrar_e2e` (usuario `e2e.comercial`) + `e2e/cotizacion-modal.spec.js` | 53-59 | `npm run test:e2e` | [x] |
| T68 | Modal del detalle a pantalla completa: formulario a la izquierda, tabla a la derecha (se mueve al modal), editar sin cerrar, «Guardar detalle» + pruebas | 55-57, 60, 61 | `e2e/cotizacion-modal.spec.js` | [x] |
| T69 | Calendarios de equipo y personales: `CalendarioCategoria.tipo/propietario`, `CalendarioMiembro`, migración 0003 (aditiva), `actividades/visibilidad.py` y vistas JSON filtradas (detalle, guardar, mover, eliminar, Gantt) + pruebas | 62-66 | `python manage.py test actividades` | [x] |
| T70 | Aviso opcional al cliente: tarea Celery `enviar_aviso_cliente`, plantilla de texto y `aviso_cliente_enviado_en` + pruebas | 67 | `python manage.py test actividades` | [x] |
| T71 | Nueva `calendario.html`, `calendario.css` y `calendario.js`: lateral con calendarios, creación rápida, formulario en dos paneles, tarjeta de detalle, bloques por calendario y solapes, modo oscuro y celular | 68-73 | Revisión visual (claro, oscuro y 390 px) | [x] |
| T72 | `sembrar_e2e` (usuario `e2e.agenda`, calendarios y eventos E2E) + `e2e/calendario.spec.js`; ajuste de `e2e/lims-correcciones.spec.js` | 63, 64, 66-71 | `npm run test:e2e` | [x] |
| T75 | `actividades/gantt_ensayos.py`: estado y avance real por línea desde `ResultadoEnsayo`, atraso contra la entrega programada, entrega de la solicitud = última fecha de sus líneas, vista del técnico + `actividades/test_gantt.py` | 74-78, 82 | `python manage.py test actividades` | [x] |
| T76 | Nueva `gantt.html`, `gantt.css` y `gantt.js`: agrupar por solicitud/técnico/cliente, filas de 34 px, cifras que filtran, carga por técnico, ficha de detalle, vista Actividades por calendario, modo oscuro y celular | 74, 79-84 | Revisión visual (claro, oscuro y 390 px) | [x] |
| T77 | `static/js/graficos_tema.js` (tema común de Chart.js) usado por `dashboard.js` y `analisis.js`; minigráficos en cotizaciones, tasa e informes del dashboard + pruebas | 85, 86 | `python manage.py test core` | [x] |
| T78 | `sembrar_e2e` (usuarios `e2e.gantt`, `e2e.tecnico.c/d`, SOL-E2E-G01..G03) + `e2e/gantt.spec.js` | 74-84 | `npm run test:e2e` | [x] |
| T79 | `proyectos/programa.py` (RN-12, 13), vistas `programa_dia`, `programa_cliente`, `programa_medidas`, medidas en lote compartidas, regreso del registro a la hoja, menús + pruebas | 87-96 | `python manage.py test proyectos.test_programa` | [x] |
| T80 | Pestañas por etapa y filtro por fecha en `/proyectos/pendientes/` (`avance.py`, RN-14, 15), búsqueda en vivo que conserva filtros + pruebas | 97-102 | `python manage.py test proyectos.test_programa` + revisión visual | [x] |
| T81 | Guardado automático: `_autoguardar` y `_autoguardar_medidas` (modo tolerante de `_aplicar_datos`), `static/js/autoguardado.js`, indicador en el registro y en «Medir y pesar», «En curso · Continuar» en Mis ensayos + `test_autoguardado.py` | 103-110 | `python manage.py test proyectos.test_autoguardado` + navegador | [x] |
| T82 | `static/js/borrador_local.js` (borrador en el equipo, restaurar/descartar, caducidad, limpieza al guardar) conectado en cotización, recepción, solicitud de ensayo y datos de probetas + `test_borrador_local.py` | 111-117 | `python manage.py test proyectos.test_borrador_local` + navegador | [x] |
| T83 | `plantilla_form.html` rehecho con pills, estado vacío y modal del detalle; estilos y modal compartidos en `servicios/includes/`; `crear_editar_plantilla` por fetch (JSON) y norma/método por código + pruebas | 118-124 | `python manage.py test servicios` + navegador | [x] |
| T84 | CSS común del panel siempre visible en `base_vicafpro.html` (25 pantallas), panel de proyectos compacto y filtro «Hoy» por movimiento (`avance.con_movimiento`) + pruebas | 99, 101, 125-128 | `python manage.py test proyectos.test_programa` + navegador (25 pantallas, celular) | [x] |
| T85 | Barra única del panel (título, controles, acciones) con botones modernos en `base_vicafpro.html`; filas propias en informes, cotizaciones y plantillas | 129-133 | Revisión visual (25 pantallas, oscuro, celular) | [x] |
| T86 | Elegir proyecto a pantalla completa (fechas, orden, avance) y modal «Registrar muestras» con tabla clara (`recepcion_muestras.js`, reemplaza `gestion_muestras.js`) | 134-140 | `proyectos/tests_recepcion_nueva.py` + navegador (escritorio y celular) | [x] |
| T87 | Solicitud de ensayo en una sola pantalla (`ensayos_form.html`, `solicitud_ensayo.js`): una fila por ensayo con varias muestras, acciones masivas, incidencias plegables, borrador | 141-147 | `proyectos/test_programa.py` (SolicitudUnaPantallaTests) + navegador | [x] |
| T88 | PDF de la solicitud en formato FOR-089 con incidencias (`ensayos_pdf.html`), lista de solicitudes por prioridad con botón de estado, pasos de resultados a la izquierda | 150-154 | `proyectos/test_programa.py` (ListaYPdfSolicitudTests) + imagen del PDF + navegador | [x] |
| T89 | Hoja de resultados del ensayo general: acepta foto del formato (cámara), botones grandes para celular, fecha de hoy por defecto | 155-157 | `proyectos/test_informe_compresion.py` + navegador móvil | [x] |
| T90 | Compresión alineada al FOR-009: foto «durante la carga» (6 fotos en 3 grupos), f'c en kg/cm² o MPa con conversión | 159-161 | `proyectos/test_compresion.py` | [x] |
| T91 | Registro único: 6 fotos para todos, pantalla con panel de fotos y formulario (PC a dos columnas, celular por pasos), formulario por servicio (`PlantillaFormulario`, `formularios_ensayo.py`), revisión e informe leen los datos | 163-170 | `proyectos/test_formulario_ensayo.py`, `test_galeria_fotos.py` + navegador | [x] |
| T92 | FOR-009 completo para todos los ensayos (`_aplicar_todo`), asistente de fotos con cámara/adjuntador único y grupos plegables | 171-175 | `proyectos/test_formulario_ensayo.py` + navegador PC y móvil | [x] |
| T93 | Registro a pantalla completa en columnas, sesión de ensayo integrada (apertura por AJAX), requisitos para terminar y fotos sin botones por recuadro | 176-180 | `proyectos/test_formulario_ensayo.py` + navegador | [x] |
| T94 | Formulario FOR-009 en modal a pantalla completa (columnas), resumen en vivo junto a las fotos, código de cliente de la cotización como solo lectura | 181-185 | `proyectos/test_formulario_ensayo.py` (FormularioEnModalTests) + navegador 100 %, 1280 y móvil | [x] |
| T95 | Registro por encima del sistema, formulario compacto en columnas, Guardar/Terminar bajo las fotos, video con casilla (`subir_video_ensayo`), alta rápida de equipos (`crear_equipo_ajax`), fotos tipo escáner, aviso de fotos de antes y resumen moderno; nginx admite 320 MB | 186-194 | `proyectos/test_formulario_ensayo.py` (VideoEquiposYDistribucionTests) + navegador 1600, tablet y móvil | [x] |
| T96 | Formulario por secciones con menú lateral (sin scroll en PC, vertical en celular), resumen como hoja FOR-009 (`hoja_estatica`, `_datos_sesion`), fotos de a dos (carrera al cerrar el recorte) y modal de sesión grande, hoja en ensayo terminado y tarjetas de ensayos en curso | 195-202 | `proyectos/test_formulario_ensayo.py` (RegistroSeccionesTests) + navegador 1600, 1366, tablet y móvil | [x] |
| T97 | Lista de resultados con en curso a la izquierda y por registrar por fecha a la derecha (`resultados_lista.css`), lista de recepciones y detalle de recepción compactos | 203-205 | `proyectos/test_compresion.py` + navegador 1850 y móvil | [x] |
| T98 | Lista de resultados en filas con pestañas separadas y conteos; se elimina el formulario «Datos de probetas» (ubicación del proyecto pasa al registro) | 206-208 | `proyectos/test_autoguardado.py`, `test_compresion.py` + navegador 1850 y móvil | [x] |
| T99 | Lista de solicitudes con conteo de ensayos, botón verde «Registrar» / ámbar «En proceso · %», pestañas por etapa y orden; pantalla de la solicitud con grupos | 209-212 | `proyectos/test_programa.py` + navegador 1850 y móvil | [x] |
| T100 | Revisión por ensayo: `revisar_ensayo` (registro de solo lectura), `marcas_revision` (migración 0015), `marcar_revision`, devolver con marcas, marcas en rojo para el técnico; entradas desde la revisión y la lista de terminados | 213-217 | `proyectos/test_informe_compresion.py` + navegador 1850 | [x] |
| T101 | PDF del informe con el diseño oficial (FOR-064 + FOR-039), QR siempre presente y cortes de página; revisión con pestañas Por revisar / Sin firmar; pantalla de informes rehecha; se elimina la emisión manual | 217-221 | `proyectos/test_informe_editor.py` + PDF renderizado y navegador | [x] |
| T102 | Revisión de solicitud a pantalla completa (`revision.css`), pantalla de envío (`enviar_informe`, `envio_informe.py`: correo inteligente y WhatsApp), `InformeFinal.canal_envio` y `mensaje_envio` (migración 0016) | 223-227 | `proyectos/test_informe_compresion.py` + navegador 1850 y móvil | [x] |
| T103 | «Añadir ensayo» en la solicitud: `api_buscar_servicios`, filas extra con buscador (`solicitud_ensayo.js`), línea «Ensayos adicionales» en la cotización (`_detalle_adicional`, ids `x<pk>`) | 228-231 | `proyectos/test_programa.py` + navegador 1850 | [x] |

## Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
| v1 | 2026-11-03 | Claude (DLF) | Tareas del dashboard |
| v2 | 2026-11-03 | Claude (DLF) | Tareas T7-T11 de Análisis |
| v3 | 2026-11-04 | Claude (DLF) | T12: nueva presentación de Análisis |
| v4 | 2026-11-22 | Claude (DLF) | T64-T65: panel de proyectos con avance por muestra |
| v5 | 2026-11-22 | Claude (DLF) | T66-T67: formulario de cotización con detalle en modal |
| v6 | 2026-11-22 | Claude (DLF) | T68: modal del detalle a pantalla completa |
| v7 | 2026-11-24 | Claude (DLF) | T69-T72: calendario rediseñado |
| v8 | 2026-11-24 | Claude (DLF) | T75-T78: Gantt de ensayos y tema común de gráficos |
| v9 | 2026-11-24 | Claude (DLF) | T79-T80: programa de ensayos del día y pestañas del panel |
| v10 | 2026-11-25 | Claude (DLF) | T81: guardado automático del registro de ensayo |
| v11 | 2026-11-25 | Claude (DLF) | T82: borrador local de formularios largos |
| v12 | 2026-11-25 | Claude (DLF) | T83: plantillas con el diseño de la cotización |
| v13 | 2026-11-25 | Claude (DLF) | T84: panel siempre visible y panel de proyectos compacto con filtro Hoy |
| v14 | 2026-11-25 | Claude (DLF) | T85: barra única del panel con botones modernos |
| v15 | 2026-11-25 | Claude (DLF) | T86: nueva recepción (elegir proyecto y registrar muestras) |
| v16 | 2026-11-25 | Claude (DLF) | T87: solicitud de ensayo en una sola pantalla |
| v17 | 2026-11-25 | Claude (DLF) | T88: PDF FOR-089, lista por prioridad y pasos de resultados |
| v18 | 2026-11-25 | Claude (DLF) | T89: hoja de resultados del ensayo general |
| v19 | 2026-11-25 | Claude (DLF) | T90: compresión alineada al FOR-009 |
| v20 | 2026-11-25 | Claude (DLF) | T91: registro único de resultados para todos los ensayos |
| v21 | 2026-11-25 | Claude (DLF) | T92: FOR-009 completo y asistente de fotos |
| v22 | 2026-11-25 | Claude (DLF) | T93: registro a pantalla completa con la sesión integrada |
| v23 | 2026-11-26 | Claude (DLF) | T94: formulario en modal y resumen junto a las fotos |
| v24 | 2026-11-26 | Claude (DLF) | T95: modal sobre todo, video, equipos, escáner y resumen moderno |
| v25 | 2026-11-26 | Claude (DLF) | T96: formulario por secciones, hoja de resumen y sesión grande |
| v26 | 2026-11-26 | Claude (DLF) | T97: lista de resultados dividida y recepciones compactas |
| v27 | 2026-11-26 | Claude (DLF) | T98: lista de resultados en filas y sin datos de probetas |
| v28 | 2026-11-26 | Claude (DLF) | T99: solicitudes con avance y pestañas por etapa |
| v29 | 2026-11-26 | Claude (DLF) | T100: revisión por ensayo con marcas en rojo |
| v30 | 2026-11-26 | Claude (DLF) | T101: informe con diseño oficial y QR, revisión e informes |
| v31 | 2026-11-26 | Claude (DLF) | T102: revisión a pantalla completa y envío inteligente |
| v32 | 2026-11-26 | Claude (DLF) | T103: añadir ensayos extra a la solicitud |
