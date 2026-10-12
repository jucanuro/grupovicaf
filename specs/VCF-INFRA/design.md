# VCF-INFRA — Design

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
| — | — | — | REQ-INFRA-?? |

## 3. Componentes y tareas Celery

| Componente / tarea | Tipo | Disparador | REQ |
|---|---|---|---|
| — | — | — | REQ-INFRA-?? |

## 4. Reglas del CLAUDE.md que aplican

| Regla CLAUDE.md | Cómo aplica |
|---|---|
| Dos procesos gunicorn por `SITE_ROLE` | Un informe pesado del LIMS no frena la web pública |
| 4. Sin `admin/` en `urls_web.py` | Nginx y los URLconf lo respetan |
| 5. Cookies de sesión aisladas | `SESSION_COOKIE_NAME = f'gv_{SITE_ROLE}_sessionid'` |
| 6. Nada de secretos en el código | `.env` fuera de Git; `.env.example` versionado sin valores |
| 7. Tareas de más de ~1 s a Celery | Servicios `worker` y `beat` en dev y prod |
| Redis: cache en DB 0, broker en DB 1 | Limpiar el cache no borra la cola |
| AWS es la fuente de verdad del LIMS | Nunca se sobrescribe desde dev; el contenido web sube con `exportar_datos_web` / `revincular_catalogo` |
| `check --deploy` antes de cada commit | `SITE_ROLE=web python manage.py check --deploy` |
| 18. 301 desde vicafpro | Redirecciones en Nginx o Django |

## 5. Riesgos

| # | Riesgo | Mitigación | Estado |
|---|---|---|---|
| R1 | `mediafiles/` está versionado en Git (71 archivos al 2026-10-11, entre ellos firmas e informes finales en PDF) | — | Pendiente de decisión |

## 6. Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
