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
| T69 | `proyectos/programa.py` (RN-12, 13), vistas `programa_dia`, `programa_cliente`, `programa_medidas`, medidas en lote compartidas, regreso del registro a la hoja, menús + pruebas | 62-71 | `python manage.py test proyectos.test_programa` | [x] |
| T70 | Pestañas por etapa y filtro por fecha en `/proyectos/pendientes/` (`avance.py`, RN-14, 15), búsqueda en vivo que conserva filtros + pruebas | 72-77 | `python manage.py test proyectos.test_programa` + revisión visual | [x] |

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
| v7 | 2026-11-24 | Claude (DLF) | T69-T70: programa de ensayos del día y pestañas del panel |
