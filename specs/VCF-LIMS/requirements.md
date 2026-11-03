# VCF-LIMS — Requirements

| Dueño | Versión | Fecha | Estado |
|---|---|---|---|
| DLF | v1 | 2026-11-03 | Aprobado (G1 del Gerente, 2026-11-03) |

> Primer alcance del módulo: **rediseño de los gráficos del dashboard** y los estados
> Enviada/Rechazada de la cotización. Origen: `proc/VCF-LIMS_HU_CU_v1.md` v1.1 del
> Proyecto de Claude (HU-LIMS-01 a 05), aprobado por el Gerente "tal cual" con las
> decisiones DP-LIMS-01 a 04 en su opción A. Mockup de referencia:
> https://claude.ai/artifact/PQkJV5aoHoZSUxkCnEWajT

## 1. Alcance

**Dentro de alcance:** `/dashboard/` del LIMS (`core.views.dashboard_view`, `templates/dashboard.html`)
y dos acciones nuevas en la lista de cotizaciones (`servicios`): marcar como enviada y marcar como rechazada.

**Fuera de alcance:**
- Zonas de cobertura distintas de Cajamarca.
- La web pública (`SITE_ROLE=web`).
- Metas comerciales (DP-LIMS-01 A: no se crea ninguna meta).
- Restringir quién aprueba una cotización (decisión del Gerente del 2026-10-30).

## 2. Requisitos (EARS)

Patrones: **CUANDO** <evento> · **MIENTRAS** <estado> · **SI** <condición> **ENTONCES** · **DONDE** <característica> + **EL SISTEMA DEBE** <respuesta>.

### Reglas de cálculo

| ID | Regla |
|---|---|
| RN-01 | **Emitida**: cotización real (`es_plantilla=False`) con `fecha_generacion` dentro del periodo, en cualquier estado. |
| RN-02 | **Enviada al cliente**: cotización emitida en estado Enviada, Aceptada o Rechazada (toda aceptada o rechazada se considera enviada). [Supuesto] |
| RN-03 | **Tasa de aceptación** = Aceptadas / (Aceptadas + Rechazadas) del periodo; con denominador 0 se muestra "Sin datos". **Conversión global** = Aceptadas / Emitidas. |
| RN-04 | **Solicitud vencida**: `SolicitudEnsayo` en `pendiente` o `proceso` con `fecha_entrega_programada` anterior a hoy (America/Lima). Es una foto de hoy: no depende del periodo. |
| RN-05 | **Cliente nuevo**: cliente cuya primera cotización real (`fecha_generacion` mínima) cae en el periodo. `Cliente` no guarda fecha de alta. |
| RN-06 | **Periodo**: `mes` (desde el día 1 del mes actual hasta hoy), `6m` (por defecto: desde el día 1 de hace 5 meses), `12m` (desde el día 1 de hace 11 meses) o `rango` (`desde`/`hasta`). El **periodo anterior** es el mismo tramo corrido N meses atrás (`mes`, `6m`, `12m`) o los mismos días inmediatamente antes (`rango`). |
| RN-07 | Fechas de referencia: cotización `fecha_generacion`, solicitud `fecha_solicitud`, proyecto `fecha_inicio`, informe `fecha_emision`, ensayo finalizado `DetalleSolicitudEnsayo.fecha_entrega_real`. |
| RN-08 | Transiciones manuales de la cotización: Pendiente → Enviada; Pendiente o Enviada → Rechazada. Aceptada solo por el flujo existente de `aprobar_cotizacion`. |

### Requisitos

| ID | HU | Requisito | Verificable (sí/no) | Origen |
|---|---|---|---|---|
| REQ-LIMS-01 | HU-LIMS-01 | CUANDO un usuario con sesión abra el dashboard, EL SISTEMA DEBE mostrar cinco indicadores: clientes registrados, cotizaciones emitidas, tasa de aceptación, solicitudes vencidas e informes por enviar. | sí (E2E) | [Validado con usuario] |
| REQ-LIMS-02 | HU-LIMS-01 | CUANDO se muestre "Clientes registrados", EL SISTEMA DEBE mostrar los clientes nuevos del periodo (RN-05) y una mini línea de clientes nuevos por mes de los últimos 12 meses. | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-03 | HU-LIMS-01 | CUANDO se muestre "Cotizaciones emitidas", EL SISTEMA DEBE mostrar la diferencia contra el periodo anterior (RN-06) con ▲, ▼ o = y en texto, nunca solo con color. | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-04 | HU-LIMS-01 | SI hay solicitudes vencidas (RN-04), ENTONCES EL SISTEMA DEBE mostrar el indicador con un ícono de alerta y el texto "Requieren atención". | sí (E2E) | [Validado con usuario] |
| REQ-LIMS-05 | HU-LIMS-01 | EL SISTEMA NO DEBE mostrar porcentajes contra una meta que no esté registrada en la base de datos. | sí (E2E) | [Decisión Gerente] DP-LIMS-01 A |
| REQ-LIMS-06 | HU-LIMS-02 | CUANDO se abra el dashboard, EL SISTEMA DEBE mostrar barras apiladas de cotizaciones por mes del periodo, separadas en Aceptadas, En gestión (Pendiente o Enviada) y Rechazadas o anuladas. | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-07 | HU-LIMS-02 | CUANDO se muestre el embudo, EL SISTEMA DEBE dibujar Emitidas, Enviadas al cliente y Aceptadas con un largo proporcional a su cantidad y mostrar entre etapas el porcentaje que avanza. | sí (E2E) | [Validado con usuario] |
| REQ-LIMS-08 | HU-LIMS-02 | EL SISTEMA DEBE mostrar cada etapa del embudo una sola vez. | sí (E2E) | [Validado con usuario] |
| REQ-LIMS-09 | HU-LIMS-02 | CUANDO el usuario pase el cursor o el foco por una barra o un punto de un gráfico, EL SISTEMA DEBE mostrar la etiqueta, la serie y la cantidad. | no en CI (canvas); se revisa a mano | [Validado con usuario] |
| REQ-LIMS-10 | HU-LIMS-02 | DONDE un gráfico no tenga datos en el periodo, EL SISTEMA DEBE mostrar "Sin datos en este periodo" en lugar del gráfico. | sí (E2E) | [Validado con usuario] |
| REQ-LIMS-11 | HU-LIMS-02 | EL SISTEMA DEBE calcular la tasa de aceptación y la conversión global según RN-03 y mostrar "Sin datos" cuando no haya cotizaciones decididas. | sí (unitaria + E2E) | [Decisión Gerente] DP-LIMS-02 A |
| REQ-LIMS-12 | HU-LIMS-03 | CUANDO se abra el dashboard, EL SISTEMA DEBE mostrar una barra segmentada con las solicitudes del periodo por estado (pendiente, en proceso, finalizado), su cantidad dentro de cada tramo y una leyenda. | sí (E2E) | [Validado con usuario] |
| REQ-LIMS-13 | HU-LIMS-03 | SI hay solicitudes vencidas, ENTONCES EL SISTEMA DEBE listar hasta 5, ordenadas por días de atraso de mayor a menor, cada una con enlace a la lista de solicitudes filtrada por su código. | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-14 | HU-LIMS-03 | CUANDO se abra el dashboard, EL SISTEMA DEBE mostrar una línea con los ensayos finalizados por semana de las últimas 12 semanas. | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-15 | HU-LIMS-03 | MIENTRAS el usuario no tenga el permiso `ensayos.ver_todos`, EL SISTEMA DEBE contar y listar como vencidas solo las solicitudes donde tiene un ensayo asignado. | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-16 | HU-LIMS-04 | CUANDO se abra el dashboard, EL SISTEMA DEBE mostrar barras horizontales proporcionales con los proyectos del periodo por etapa, tomada de `Proyecto.estado`, con Cancelado en gris. | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-17 | HU-LIMS-05 | CUANDO el usuario elija un periodo, EL SISTEMA DEBE recalcular todos los indicadores y gráficos con ese periodo (RN-06). | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-18 | HU-LIMS-05 | EL SISTEMA DEBE ofrecer en cada gráfico un "Ver como tabla" con los mismos datos. | sí (E2E) | [Validado con usuario] |
| REQ-LIMS-19 | HU-LIMS-05 | EL SISTEMA DEBE cargar la librería de gráficos (Chart.js 4.4.1) desde `static/` con `defer`, sin scripts de CDN propios del dashboard en el `<head>`. | sí (unitaria) | [Decisión Gerente] DP-LIMS-04 A |
| REQ-LIMS-20 | HU-LIMS-05 | CUANDO el ancho de pantalla sea de celular (390 px), EL SISTEMA DEBE apilar indicadores y gráficos sin desplazamiento horizontal. | sí (E2E) | [Validado con usuario] |
| REQ-LIMS-21 | HU-LIMS-05 | EL SISTEMA DEBE calcular el dashboard con un número de consultas que no crezca con la cantidad de proyectos. | sí (unitaria, `assertNumQueries` estable) | [Propuesto] (corrige E-10) |
| REQ-LIMS-22 | HU-LIMS-02 | CUANDO un usuario con `cotizaciones.ver` marque como enviada una cotización Pendiente, EL SISTEMA DEBE pasarla a Enviada y avisar con un mensaje. | sí (unitaria + E2E) | [Decisión Gerente] DP-LIMS-03 A |
| REQ-LIMS-23 | HU-LIMS-02 | CUANDO un usuario con `cotizaciones.ver` marque como rechazada una cotización Pendiente o Enviada, EL SISTEMA DEBE pasarla a Rechazada y avisar con un mensaje. | sí (unitaria + E2E) | [Decisión Gerente] DP-LIMS-03 A |
| REQ-LIMS-24 | HU-LIMS-02 | SI la transición no está permitida por RN-08 o la petición no es POST, ENTONCES EL SISTEMA DEBE dejar el estado sin cambios y no mostrar el botón cuando la transición no aplica. | sí (unitaria + E2E) | [Propuesto] |
| REQ-LIMS-25 | HU-LIMS-02 | EL SISTEMA DEBE excluir las plantillas de cotización (`es_plantilla=True`) de todos los indicadores. | sí (unitaria) | [Propuesto] (E-12, hallado al implementar) |
| REQ-LIMS-26 | HU-LIMS-05 | EL SISTEMA DEBE cargar el dashboard en menos de 1 s con 1 000 proyectos. | no en CI; se mide a mano | [Propuesto] |

## 3. Trazabilidad HU → REQ

| HU | Descripción | REQ |
|---|---|---|
| HU-LIMS-01 | Indicadores clave con contexto | REQ-LIMS-01 a 05 |
| HU-LIMS-02 | Evolución y embudo comercial | REQ-LIMS-06 a 11, 22 a 25 |
| HU-LIMS-03 | Estado del laboratorio | REQ-LIMS-12 a 15 |
| HU-LIMS-04 | Proyectos por etapa | REQ-LIMS-16 |
| HU-LIMS-05 | Filtro único, accesibilidad y rendimiento | REQ-LIMS-17 a 21, 26 |

## 4. Preguntas abiertas

| # | Pregunta | Responsable | Estado |
|---|---|---|---|
| 1 | Al leer `Proyecto.estado` (REQ-LIMS-16) los números pueden diferir del dashboard anterior, que recalculaba la etapa. Comparar en producción antes del pase (PM-02). | Gerente | Abierta |

## 5. Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
| v1 | 2026-11-03 | Claude (DLF) | Alcance del dashboard y estados de cotización: RN-01 a 08, REQ-LIMS-01 a 26 |
