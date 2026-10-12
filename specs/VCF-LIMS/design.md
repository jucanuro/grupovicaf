# VCF-LIMS — Design

| Dueño | Versión | Fecha | Estado |
|---|---|---|---|
| DLF | v0 | 2026-10-12 | Plantilla, bloqueado hasta G1 |

> Depende de `requirements.md` aprobado (G1). Todo elemento de este diseño apunta a un REQ.

## 1. Modelo de datos

```mermaid
erDiagram
    %% PENDIENTE: entidades y relaciones
```

## 2. Vistas y URLs

| URL | Vista | Permiso | REQ |
|---|---|---|---|
| — | — | — | REQ-LIMS-?? |

## 3. Componentes y tareas Celery

| Componente / tarea | Tipo | Disparador | REQ |
|---|---|---|---|
| — | — | — | REQ-LIMS-?? |

## 4. Reglas del CLAUDE.md que aplican

| Regla CLAUDE.md | Cómo aplica |
|---|---|
| Apps LIMS: NO renombrar, NO romper migraciones | `core`, `clientes`, `trabajadores`, `servicios`, `proyectos`, `actividades` conservan su label y su historial de migraciones |
| 1. Nunca duplicar modelos del LIMS | El LIMS es la fuente única de `Cliente`, `Servicio`, `TrabajadorProfile` |
| 3. Campos prohibidos en respuestas públicas | Los modelos del LIMS no exponen `codigo_confidencial`, `ruc`, `firma_electronica`, `monto_cotizacion` ni `codigo_voucher` fuera del LIMS |
| 4. Admin solo en `urls_lab.py` | Toda vista de administración vive en el LIMS |
| 5. Cookies de sesión aisladas | `gv_lab_sessionid` |
| 6. Nada de secretos en el código | Configuración por `.env` |
| 7. Tareas de más de ~1 s a Celery | PDF de informes, QR, correo, SMS |
| 8. `AUTH_USER_MODEL` por defecto | No cambiarlo: lo usan migraciones ya aplicadas de `actividades` y `proyectos` |
| 15. `noindex` en `/proyectos/v/` | Validación de informes y vistas con datos de cliente fuera del sitemap |

## 5. Riesgos

| # | Riesgo | Mitigación | Estado |
|---|---|---|---|
| R1 | Una migración nueva rompe datos ya aplicados en AWS | — | Pendiente |

## 6. Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
