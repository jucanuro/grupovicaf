# VCF-LIMS — Tasks

| Dueño | Versión | Fecha | Estado |
|---|---|---|---|
| DLF | v1 | 2026-11-03 | En curso |

> Depende de `design.md` v1. Cada tarea cubre al menos un REQ y se verifica antes de marcarla `[x]`.

**Formato de commit:** `VCF-LIMS T<n>: <qué>`.

| T | Tarea | REQ | Verificación | Estado |
|---|---|---|---|---|
| T1 | Spec SDD del dashboard (requirements, design, tasks) | todos | Revisión del Gerente (G1 dado el 2026-11-03) | [x] |
| T2 | `core/dashboard.py` con periodo, KPI, series y agregaciones + pruebas unitarias | 01-03, 06, 11, 13-17, 21, 25 | `python manage.py test core` | [ ] |
| T3 | Transiciones Enviada/Rechazada de la cotización (vistas, URLs, botones) + pruebas | 22-24 | `python manage.py test servicios` | [ ] |
| T4 | Chart.js 4.4.1 en `static/vendor/` y `static/js/dashboard.js` | 06, 09, 14, 19 | Prueba unitaria del HTML + revisión visual | [ ] |
| T5 | Nueva `templates/dashboard.html` (filtro, KPI, comercial, laboratorio, proyectos, tablas, vacíos, responsive) | 01-20 | E2E | [ ] |
| T6 | `sembrar_e2e` con cotizaciones, solicitudes vencidas y proyectos + `e2e/dashboard.spec.js` | 01-08, 10-18, 20, 22-24 | `npm run test:e2e` | [ ] |

## Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
| v1 | 2026-11-03 | Claude (DLF) | Tareas del dashboard |
