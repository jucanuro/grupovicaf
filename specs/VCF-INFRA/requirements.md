# VCF-INFRA — Requirements

| Dueño | Versión | Fecha | Estado |
|---|---|---|---|
| DLF | v0 | 2026-10-12 | Plantilla, bloqueado hasta G1 |

> Plantilla. No se escribe código de este módulo hasta que este documento pase el gate G1.

## 1. Alcance

**Dentro de alcance:** Docker, gunicorn por SITE_ROLE, Celery/beat, Redis, Postgres, Nginx, Certbot, backups y despliegue en EC2 — _PENDIENTE: detallar._

**Fuera de alcance:**
- Zonas de cobertura distintas de Cajamarca.

## 2. Requisitos (EARS)

Patrones: **CUANDO** <evento> · **MIENTRAS** <estado> · **SI** <condición> **ENTONCES** · **DONDE** <característica> + **EL SISTEMA DEBE** <respuesta>.

| ID | HU | Requisito | Verificable (sí/no) | Origen |
|---|---|---|---|---|
| REQ-INFRA-01 | — | CUANDO se ejecute `python manage.py test` con `SITE_ROLE=lab` o `SITE_ROLE=web`, EL SISTEMA DEBE correr los tests de las apps `web_*` contra `grupovicaf/urls_web.py`, de modo que el resultado de la suite no dependa del rol. | Sí: la suite pasa con los dos roles | [Decisión Gerente] 2026-10-23 |
| REQ-INFRA-02 | — | CUANDO se abra o actualice un PR contra `dev` o `main`, EL SISTEMA DEBE levantar los sitios lab y web con datos fijos (`sembrar_e2e`) y recorrer en un navegador real los flujos cubiertos en `e2e/`; SI una prueba falla, ENTONCES el job `e2e` del CI DEBE quedar en rojo. | Sí: job `e2e` del CI | [Decisión Gerente] 2026-10-30 (aprobó montar Playwright) |

## 3. Trazabilidad HU → REQ

| HU | Descripción | REQ |
|---|---|---|
| HU-?? | — | REQ-INFRA-01 |
| — | Evidencia automática para el gate G4 (QA) | REQ-INFRA-02 |

## 4. Preguntas abiertas

| # | Pregunta | Responsable | Estado |
|---|---|---|---|
| 1 | — | — | Abierta |

## 5. Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
| v0.1 | 2026-10-23 | DLF | REQ-INFRA-01 por [Decisión Gerente] (tests independientes del SITE_ROLE); el resto sigue en G0 |
| v0.2 | 2026-10-30 | DLF | REQ-INFRA-02 (pruebas E2E con Playwright) |
