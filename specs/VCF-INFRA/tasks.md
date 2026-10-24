# VCF-INFRA — Tasks

| Dueño | Versión | Fecha | Estado |
|---|---|---|---|
| DLF | v0 | 2026-10-12 | Plantilla, bloqueado hasta G1 |

> Depende de `design.md` revisado. Cada tarea cubre al menos un REQ y se verifica antes de marcarla `[x]`.

**Formato de commit:** `VCF-INFRA T<n>: <qué>`, por ejemplo `VCF-INFRA T1: <qué>`.

| T | Tarea | REQ | Verificación | Estado |
|---|---|---|---|---|
| T1 | Tests web independientes del `SITE_ROLE`: `grupovicaf/test_runner.py` (`SiteRoleTestRunner`) y `TEST_RUNNER` en `settings/base.py` | REQ-INFRA-01 | `SITE_ROLE=lab` y `SITE_ROLE=web python manage.py test` en verde (antes: 35 `NoReverseMatch` con `lab`) | [x] |

## Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
| v0.1 | 2026-10-23 | DLF | T1 por [Decisión Gerente] |
