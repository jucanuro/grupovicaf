# VCF-LIMS — Requirements

| Dueño | Versión | Fecha | Estado |
|---|---|---|---|
| DLF | v2 | 2026-11-03 | Aprobado (G1 del Gerente, 2026-11-03) |

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

## 2b. Análisis con tabla dinámica (v2)

Origen: `proc/VCF-LIMS_HU_CU_analisis_v3.md` (HU-LIMS-06 a 10), G1 del Gerente el
2026-11-03 con todas las recomendaciones (DP-LIMS-05 A PivotTable.js + Chart.js,
06 A .xlsx con SheetJS, 08 A permiso `reportes.ver`, 11 A vistas guardadas por
usuario, 12 B permiso del módulo por conjunto) y entrega en dos PR. **PR 1:**
motor + conjuntos Cotizaciones, Ítems cotizados y Clientes. **PR 2:** Muestras,
Solicitudes, Ensayos asignados, Incidencias, Informes, Proyectos, Actividades y
Bandeja web. Fuera de alcance: varios pagos por cotización, detracción, fecha de
pago y aprobación a crédito (PM-R01); por eso cobrado y saldo son "referenciales".

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-27 | HU-LIMS-06 | CUANDO un usuario con `reportes.ver` abra `/analisis/`, EL SISTEMA DEBE mostrar un selector con los conjuntos que su rol puede ver y abrir el primero con su rango por defecto y su primera vista rápida. | sí (unitaria + E2E) | [Decisión Gerente] |
| REQ-LIMS-28 | HU-LIMS-06 | CUANDO el usuario arrastre un campo a filas o columnas o cambie el cálculo (Cantidad, Suma, Promedio, Mínimo, Máximo), EL SISTEMA DEBE recalcular la tabla con totales sin recargar la página. | sí (E2E) | [Propuesto] |
| REQ-LIMS-29 | HU-LIMS-06 | EL SISTEMA DEBE filtrar cada conjunto por su fecha principal (Cotizaciones e Ítems: `fecha_generacion`; Clientes: `creado_en`) y excluir las plantillas. | sí (unitaria + E2E) | [Propuesto] |
| REQ-LIMS-30 | HU-LIMS-06 | SI "desde" es posterior a "hasta" o la fecha no es AAAA-MM-DD, ENTONCES EL SISTEMA DEBE avisarlo y no calcular; SI no hay filas, ENTONCES EL SISTEMA DEBE mostrar "Sin datos para estos filtros". | sí (unitaria + E2E) | [Propuesto] |
| REQ-LIMS-31 | HU-LIMS-06 | EL SISTEMA DEBE calcular Cobrado = `Voucher.monto_pagado` y Saldo referencial = total − cobrado solo para Aceptadas, nunca negativo. | sí (unitaria) | [Propuesto] RN-R02 |
| REQ-LIMS-32 | HU-LIMS-07 | CUANDO el usuario elija Barras, Barras apiladas, Líneas o Dona, EL SISTEMA DEBE dibujar el mismo resultado con Chart.js, con leyenda si hay más de una serie y tooltip con el valor. | sí (E2E) | [Decisión Gerente] |
| REQ-LIMS-33 | HU-LIMS-07 | SI hay más de 20 categorías u 8 series, ENTONCES EL SISTEMA DEBE agrupar el resto en "Otros" y avisarlo; DONDE se elija Dona con columnas, EL SISTEMA DEBE avisar que usa el total por fila. | sí (E2E para la dona) | [Propuesto] |
| REQ-LIMS-34 | HU-LIMS-08 | EL SISTEMA DEBE ofrecer vistas rápidas por conjunto y ocultar las que usen campos que el usuario no puede ver. | sí (unitaria + E2E) | [Propuesto] |
| REQ-LIMS-35 | HU-LIMS-08 | CUANDO el usuario guarde una vista con nombre, EL SISTEMA DEBE guardar solo la disposición (filas, columnas, cálculo, filtros) para ese usuario; cada usuario ve y elimina solo las suyas. | sí (unitaria + E2E) | [Decisión Gerente] DP-LIMS-11 A |
| REQ-LIMS-36 | HU-LIMS-08 | EL SISTEMA DEBE reflejar conjunto, rango y disposición en la URL para que el enlace abra la misma tabla. | sí (E2E) | [Propuesto] |
| REQ-LIMS-37 | HU-LIMS-09 | CUANDO el usuario pulse "Exportar a Excel" o "Exportar datos", EL SISTEMA DEBE descargar un .xlsx con cabecera (conjunto, rango, filas, columnas, cálculo, filtros, fecha) y montos como números. | sí (E2E) | [Decisión Gerente] DP-LIMS-06 A |
| REQ-LIMS-38 | HU-LIMS-10 | SI el usuario no tiene `reportes.ver`, ENTONCES EL SISTEMA DEBE responder 403 y ocultar el menú; SI no tiene el permiso de ver del módulo del conjunto, ENTONCES EL SISTEMA DEBE ocultar el conjunto y responder 403 a sus datos; los montos de Clientes exigen además `cotizaciones.ver`. | sí (unitaria + E2E) | [Decisión Gerente] DP-LIMS-08 A, 12 B |
| REQ-LIMS-39 | HU-LIMS-10 | EL SISTEMA NO DEBE enviar al navegador campos fuera de la lista blanca del conjunto (nunca RUC, código confidencial, firmas, archivos, código del voucher ni contactos). | sí (unitaria por conjunto) | [Propuesto] |
| REQ-LIMS-40 | HU-LIMS-10 | EL SISTEMA DEBE entregar los datos con un número fijo de consultas y rechazar rangos de más de 20 000 filas pidiendo acotarlos. | sí (unitaria) | [Propuesto] |
| REQ-LIMS-41 | HU-LIMS-06 | EL SISTEMA DEBE mostrar los conjuntos como un menú agrupado por módulo y, al abrir uno, sus campos en "Agrupar por" y "Medir", que el usuario arrastra o toca para llevarlos a Filas, Columnas, Valores o Filtros. | sí (E2E) | [Decisión Gerente] |
| REQ-LIMS-42 | HU-LIMS-06 | EL SISTEMA DEBE mostrar cada número según su tipo: montos en S/ con dos decimales, conteos y cantidades sin decimales de más, días y porcentajes con un decimal en promedios; y elegir el cálculo al soltar (montos y cantidades se suman, días y % se promedian). | sí (unitaria JS + E2E) | [Decisión Gerente] |
| REQ-LIMS-43 | HU-LIMS-08 | EL SISTEMA DEBE explicar el resultado con una frase y mostrar los totales antes de la tabla, y ofrecer las vistas rápidas como preguntas frecuentes. | sí (E2E) | [Decisión Gerente] |

## 3. Trazabilidad HU → REQ

| HU | Descripción | REQ |
|---|---|---|
| HU-LIMS-01 | Indicadores clave con contexto | REQ-LIMS-01 a 05 |
| HU-LIMS-02 | Evolución y embudo comercial | REQ-LIMS-06 a 11, 22 a 25 |
| HU-LIMS-03 | Estado del laboratorio | REQ-LIMS-12 a 15 |
| HU-LIMS-04 | Proyectos por etapa | REQ-LIMS-16 |
| HU-LIMS-05 | Filtro único, accesibilidad y rendimiento | REQ-LIMS-17 a 21, 26 |
| HU-LIMS-06 | Tabla dinámica | REQ-LIMS-27 a 31 |
| HU-LIMS-07 | Ver como gráfico | REQ-LIMS-32, 33 |
| HU-LIMS-08 | Vistas rápidas y guardadas | REQ-LIMS-34 a 36 |
| HU-LIMS-09 | Exportar | REQ-LIMS-37 |
| HU-LIMS-10 | Seguridad y rendimiento | REQ-LIMS-38 a 40 |

## 4. Preguntas abiertas

| # | Pregunta | Responsable | Estado |
|---|---|---|---|
| 1 | Al leer `Proyecto.estado` (REQ-LIMS-16) los números pueden diferir del dashboard anterior, que recalculaba la etapa. Comparar en producción antes del pase (PM-02). | Gerente | Abierta |

## 5. Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
| v1 | 2026-11-03 | Claude (DLF) | Alcance del dashboard y estados de cotización: RN-01 a 08, REQ-LIMS-01 a 26 |
| v2 | 2026-11-03 | Claude (DLF) | Análisis con tabla dinámica (PR 1): REQ-LIMS-27 a 40 |
