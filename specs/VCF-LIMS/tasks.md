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
| T11 | PR 2: conjuntos Muestras, Solicitudes, Ensayos asignados, Incidencias, Informes, Proyectos, Actividades y Bandeja web | 27, 29, 38, 39 | Unitarias por conjunto + E2E | [ ] |

## Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
| v1 | 2026-11-03 | Claude (DLF) | Tareas del dashboard |
| v2 | 2026-11-03 | Claude (DLF) | Tareas T7-T11 de Análisis |
