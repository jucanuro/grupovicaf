# VCF-WEB — Design

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
| — | — | — | REQ-WEB-?? |

## 3. Componentes y tareas Celery

| Componente / tarea | Tipo | Disparador | REQ |
|---|---|---|---|
| — | — | — | REQ-WEB-?? |

## 4. Reglas del CLAUDE.md que aplican

| Regla CLAUDE.md | Cómo aplica |
|---|---|
| Prefijo `web_` obligatorio | Toda app pública nueva lleva el prefijo |
| 1. Nunca duplicar modelos del LIMS | Solo modelos companion con `OneToOneField` (ej. `ServicioPublicado`) |
| 2. Lista blanca de campos | `.only()` / `.values()` con campos explícitos en toda vista pública |
| 3. Campos prohibidos | Ninguna respuesta pública incluye `codigo_confidencial`, `ruc`, `firma_electronica`, `monto_cotizacion`, `codigo_voucher` ni cotizaciones ajenas |
| 4. Sin `admin/` en `urls_web.py` | El admin vive solo en el LIMS |
| 5. Cookies de sesión aisladas | `gv_web_sessionid` |
| 7. Tareas de más de ~1 s a Celery | Correos de contacto y cotización |
| 9–10. Un H1 y una keyword por URL | Verificar que la keyword no esté asignada antes de crear una página |
| 11. `SeoModel` | Todo modelo con página propia hereda de `grupovicaf/seo.py` |
| 12. Canonical absoluto con `SITE_URL` | En toda página |
| 13. JSON-LD | `LocalBusiness`, `Service`, `FAQPage`, `BreadcrumbList`, `JobPosting` según el tipo |
| 14. NAP consistente | Un solo origen de nombre, dirección y teléfono |
| 15. `noindex` en `/portal/` | Fuera del sitemap |
| 16. Sin doorway pages | Contenido de zona/servicio sin redactar → placeholder PENDIENTE DE REDACCIÓN |
| 17. Rendimiento | CSS purgado, imágenes con dimensiones y `lazy`, `font-display: swap` |
| 18. 301 desde vicafpro | Toda URL que cambie |

## 5. Riesgos

| # | Riesgo | Mitigación | Estado |
|---|---|---|---|
| R1 | Una vista pública filtra campos prohibidos del LIMS | — | Pendiente |

## 6. Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
