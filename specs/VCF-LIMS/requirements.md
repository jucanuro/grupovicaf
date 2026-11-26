# VCF-LIMS — Requirements

| Dueño | Versión | Fecha | Estado |
|---|---|---|---|
| DLF | v6 | 2026-11-24 | Aprobado (G1 del Gerente, 2026-11-03; 2e aprobado en el hilo el 2026-11-24) |

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

## 2c. Panel de proyectos con avance por muestra (v3)

Origen: pedido del Gerente del 2026-11-22 en el hilo «Rediseñar dashboard con
avance por muestra», aprobado sobre el segundo mockup («me gusta, impleméntalo»).
Pantalla: `/proyectos/pendientes/` (menú «Proyectos»). HU-LIMS-19: *como jefe de
laboratorio quiero ver, por proyecto, en qué etapa está cada muestra y la acción
más urgente, para no perder ninguna muestra en el flujo*.

| ID | Regla |
|---|---|
| RN-09 | Etapa de una muestra (`MuestraDetalle`): **Con informe** si la solicitud de su recepción tiene `InformeFinal`; si no, **En ensayo** si tiene una línea `DetalleSolicitudEnsayo`; si no, **Recibida**. **Por ingresar** = `Proyecto.numero_muestras` − muestras registradas (nunca negativo). [Supuesto] una fila de `MuestraDetalle` = una muestra, igual que `sembrar_demo` y Análisis. |
| RN-10 | % de avance = Σ peso de cada muestra / (total × 3), con pesos Por ingresar 0, Recibida 1, En ensayo 2, Con informe 3. Total = previstas o registradas, la mayor. [Propuesto] |
| RN-11 | Acción más urgente, en orden: registrar las que faltan → revisar y emitir el informe de una solicitud finalizada sin informe → asignar ensayos a las recibidas → seguir las que están en ensayo → ver informes (proyecto completo). [Propuesto] |

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-44 | HU-LIMS-19 | CUANDO un usuario con `proyectos.ver` abra el panel de proyectos, EL SISTEMA DEBE mostrar por proyecto el % de avance (RN-10) con una barra en degradado verde → azul. | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-45 | HU-LIMS-19 | EL SISTEMA DEBE mostrar por proyecto cuatro etapas en orden del flujo (Por ingresar, Recibidas, En ensayo, Con informe) con la cantidad de muestras de cada una (RN-09). | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-46 | HU-LIMS-19 | CUANDO el usuario pulse una etapa, EL SISTEMA DEBE abrir su pantalla acotada al proyecto: Por ingresar → nueva recepción del proyecto; Recibidas → recepciones; En ensayo → solicitudes; Con informe → informes (`?proyecto=<id>`, con aviso del filtro y «Ver todos»). | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-47 | HU-LIMS-19 | EL SISTEMA DEBE mostrar un botón destacado con la acción más urgente (RN-11) que lleve a su pantalla. | sí (unitaria + E2E) | [Validado con usuario] |
| REQ-LIMS-48 | HU-LIMS-19 | SI una solicitud del proyecto está finalizada sin informe y no faltan muestras, ENTONCES EL SISTEMA DEBE ofrecer «Revisar y emitir informe» hacia la revisión de esa solicitud. | sí (unitaria) | [Propuesto] |
| REQ-LIMS-49 | HU-LIMS-19 | SI el proyecto no tiene cotización, ENTONCES EL SISTEMA DEBE mostrar «Sin cotización vinculada» sin etapas ni acción. | sí (unitaria) | [Propuesto] |
| REQ-LIMS-50 | HU-LIMS-19 | CUANDO todas las muestras tengan informe, EL SISTEMA DEBE mostrar «Completo» en lugar del % y la acción «Ver informes». | sí (unitaria) | [Propuesto] |
| REQ-LIMS-51 | HU-LIMS-19 | SI el usuario no tiene el permiso de la pantalla de una etapa o de la acción, ENTONCES EL SISTEMA DEBE mostrarla sin enlace. | sí (unitaria + E2E) | [Propuesto] |
| REQ-LIMS-52 | HU-LIMS-19 | EL SISTEMA DEBE calcular el avance de una página del panel con un número fijo de consultas. | sí (unitaria) | [Propuesto] |

## 2d. Formulario de cotización: pasos en pills y detalle en modal (v4)

Origen: pedido del Gerente del 2026-11-22 en el hilo «Rediseñar formulario de
cotización con modal», aprobado sobre el mockup («del resto de los tabs dale el
mismo diseño»). Pantallas: `/servicios/cotizaciones/crear/` y
`/servicios/cotizaciones/editar/<id>/`. HU-LIMS-20: *como comercial quiero
llenar el detalle de la cotización en una ventana amplia, para elegir servicios
con comodidad*. Solo cambia la presentación: agregar, editar, ordenar y quitar
ítems, el total y las validaciones al guardar siguen igual.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-53 | HU-LIMS-20 | EL SISTEMA DEBE mostrar los 4 pasos (Cliente, Servicios, Condiciones, Contenido) como pills redondeadas con su número; el paso activo con fondo en degradado azul → índigo y texto blanco, los demás en gris claro. | sí (E2E) | [Decisión Gerente] |
| REQ-LIMS-54 | HU-LIMS-20 | MIENTRAS el detalle no tenga ítems, EL SISTEMA DEBE mostrar en el paso Servicios un estado vacío con un solo botón «Agregar detalle», sin el panel de selección ni la tabla. | sí (E2E) | [Decisión Gerente] |
| REQ-LIMS-55 | HU-LIMS-20 | CUANDO el usuario pulse «Agregar detalle», EL SISTEMA DEBE abrir un modal a pantalla completa con el formulario (categoría, sub-categoría, servicio, norma, método, cantidad y precio) apilado a la izquierda y la tabla del detalle a la derecha, ocupando el resto del ancho (el formulario usa cerca de un tercio, entre 380 y 640 px). | sí (E2E) | [Decisión Gerente] |
| REQ-LIMS-56 | HU-LIMS-20 | CUANDO el usuario pulse «Agregar a la tabla», EL SISTEMA DEBE añadir el ítem a la tabla del modal sin cerrarlo; CUANDO pulse «Guardar detalle», EL SISTEMA DEBE cerrar el modal y mostrar en el paso Servicios solo la tabla con un botón «Editar» por fila. | sí (E2E) | [Decisión Gerente] |
| REQ-LIMS-57 | HU-LIMS-20 | CUANDO el usuario pulse «Editar» en una fila (del paso Servicios o de la tabla del modal), EL SISTEMA DEBE abrir el modal, cargar la fila en el formulario, resaltarla y, al «Actualizar ítem», reemplazarla sin cerrar el modal. | sí (E2E) | [Decisión Gerente] |
| REQ-LIMS-58 | HU-LIMS-20 | SI el usuario pulsa «Agregar a la tabla» sin elegir un servicio, ENTONCES EL SISTEMA DEBE avisarlo dentro del modal sin cerrarlo. | sí (E2E) | [Propuesto] |
| REQ-LIMS-59 | HU-LIMS-20 | DONDE la pantalla mida menos de 768 px, EL SISTEMA DEBE mostrar el modal a pantalla completa y sin desplazamiento horizontal. | sí (E2E) | [Propuesto] |
| REQ-LIMS-60 | HU-LIMS-20 | SI al pulsar «Guardar detalle» hay un servicio elegido sin agregar, ENTONCES EL SISTEMA DEBE agregarlo (o actualizar la fila en edición) antes de cerrar. | sí (E2E) | [Propuesto] |
| REQ-LIMS-61 | HU-LIMS-20 | MIENTRAS se edita una fila, EL SISTEMA DEBE ofrecer «Cancelar edición», que vuelve el formulario a «Agregar ítem» sin cambiar la fila. | sí (E2E) | [Propuesto] |

## 2e. Calendario: calendarios de equipo y personales, formulario en dos paneles (v6)

Origen: pedido del Gerente del 2026-11-23 (calendarios como «Supervisión DICAP»,
personales «Casa / Personal / Estudio», cliente solo de referencia, aviso
opcional, todo en una ventana, vista semanal tipo Google) y capturas de su
calendario de Apple del 2026-11-24; mockups aprobados («Procede con el
desarrollo», 2026-11-24). Pantalla: `/actividades/calendario/`. HU-LIMS-21:
*como coordinador quiero agendar en calendarios de equipo y personales con
pocos clics, para que cada quien vea solo lo que le toca*.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-62 | HU-LIMS-21 | EL SISTEMA DEBE manejar dos tipos de calendario: de equipo (con miembros que ven o ven y crean) y personal (de un solo usuario). Un calendario de equipo sin miembros lo ven todos los que tienen `calendario.ver`. | sí (unitaria) | [Decisión Gerente] |
| REQ-LIMS-63 | HU-LIMS-21 | EL SISTEMA DEBE mostrar un calendario personal y sus eventos solo a su dueño, también frente al superusuario. | sí (unitaria + E2E) | [Decisión Gerente] |
| REQ-LIMS-64 | HU-LIMS-21 | CUANDO una actividad tenga participantes, EL SISTEMA DEBE mostrarla solo a sus participantes y a quien la creó; si no tiene, a quienes ven su calendario. | sí (unitaria + E2E) | [Decisión Gerente] |
| REQ-LIMS-65 | HU-LIMS-21 | SI el usuario no ve una actividad, ENTONCES EL SISTEMA DEBE responder 404 al ver su detalle, moverla o eliminarla; SI la ve pero no puede crear en su calendario, ENTONCES DEBE responder 403 al guardarla, moverla o eliminarla. | sí (unitaria) | [Propuesto] |
| REQ-LIMS-66 | HU-LIMS-21 | EL SISTEMA DEBE permitir guardar una actividad sin cliente (actividad interna); el cliente es solo referencia y no se invita. | sí (unitaria + E2E) | [Decisión Gerente] |
| REQ-LIMS-67 | HU-LIMS-21 | DONDE el usuario marque «Enviar aviso al cliente por correo» y el cliente tenga correo, EL SISTEMA DEBE enviarle por Celery el título, fecha, hora, lugar, enlace y descripción (nunca las observaciones internas) y registrar cuándo se envió; SI el cliente no tiene correo, ENTONCES DEBE rechazar la casilla (400). | sí (unitaria + E2E) | [Decisión Gerente] |
| REQ-LIMS-68 | HU-LIMS-21 | EL SISTEMA DEBE mostrar el formulario en una sola ventana con dos paneles: campos a la izquierda y vista previa, resumen y choques de horario a la derecha; sin el campo «categoría» (lo reemplaza el calendario). | sí (E2E) | [Decisión Gerente] |
| REQ-LIMS-69 | HU-LIMS-21 | CUANDO el usuario arrastre o pulse un hueco del calendario, EL SISTEMA DEBE abrir una creación rápida (título y calendario) con «Más opciones» hacia el formulario completo. | sí (E2E) | [Propuesto] |
| REQ-LIMS-70 | HU-LIMS-21 | EL SISTEMA DEBE mostrar en la vista semanal cada evento como bloque con título y hora, del color de su calendario, y los eventos que se cruzan lado a lado sin tapar el título. | sí (E2E) | [Decisión Gerente] |
| REQ-LIMS-71 | HU-LIMS-21 | EL SISTEMA DEBE ofrecer vistas Día, Semana, Mes y Lista, mini mes, filtro por calendario, «Solo donde participo», «Vencidas» y búsqueda; y recordar la vista y los calendarios ocultos en el navegador. | sí (E2E) | [Propuesto] |
| REQ-LIMS-72 | HU-LIMS-21 | CUANDO el usuario mueva o cambie la duración de un evento, EL SISTEMA DEBE guardarlo y ofrecer «Deshacer». | revisión visual | [Propuesto] |
| REQ-LIMS-73 | HU-LIMS-21 | DONDE la pantalla mida menos de 900 px, EL SISTEMA DEBE abrir en vista Día, con el panel lateral plegable y un botón flotante para crear. | revisión visual | [Propuesto] |

## 2f. Gantt de ensayos y tema común de gráficos (v7)

Origen: pedido del Gerente del 2026-11-24 («tomar como referencia el diseño
del calendario y darle el mismo estilo al Gantt y mejorar la presentación de
gráficos»; luego «la prioridad son los ensayos, se ven muy llenos»). Mockups
v2 aprobados el 2026-11-24 («programa entonces aprobado»), con las decisiones
DP-01 a DP-04 tal como se recomendaron. Pantalla: `/actividades/gantt/`.
HU-LIMS-22: *como jefe de laboratorio quiero ver en una línea de tiempo cada
ensayo de cada solicitud, su avance real y su atraso, para saber qué está por
vencer sin abrir cada solicitud*. HU-LIMS-23: *como Gerente quiero que los
gráficos del dashboard y de Análisis tengan un mismo estilo, legible en claro
y en oscuro*.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-74 | HU-LIMS-22 | EL SISTEMA DEBE abrir el Gantt en la vista «Ensayos», agrupado por solicitud: una fila de encabezado con el código, el cliente, «n/m listos» y la fecha de entrega, y debajo una fila por línea de ensayo con la muestra, el ensayo y el técnico. | sí (E2E) | [Decisión Gerente] DP-02 |
| REQ-LIMS-75 | HU-LIMS-22 | EL SISTEMA DEBE calcular el avance de cada línea con su resultado: 0 % sin resultado, 100 % terminado o aprobado y, en registro, la parte de los datos y fotos obligatorios ya cargados (entre 5 y 95 %). | sí (unitaria) | [Decisión Gerente] DP-01 |
| REQ-LIMS-76 | HU-LIMS-22 | EL SISTEMA DEBE pintar cada línea según su propio estado: sin empezar (borde punteado), en registro o devuelta (ámbar), terminada o aprobada (verde). | sí (unitaria + E2E) | [Propuesto] |
| REQ-LIMS-77 | HU-LIMS-22 | MIENTRAS una línea no esté terminada y su entrega programada ya haya pasado, EL SISTEMA DEBE mostrar una franja de atraso desde esa fecha hasta hoy con los días de retraso, y contarla en «Atrasados». | sí (unitaria + E2E) | [Propuesto] |
| REQ-LIMS-78 | HU-LIMS-22 | EL SISTEMA DEBE marcar la entrega de cada solicitud con un rombo en la última `fecha_entrega_programada` de sus líneas. | sí (unitaria) | [Decisión Gerente] DP-03 [Supuesto] |
| REQ-LIMS-79 | HU-LIMS-22 | EL SISTEMA DEBE mostrar arriba cuántas líneas están en proceso, cuántas se entregan esta semana, cuántas están atrasadas y cuántas se terminaron en el mes, según los filtros. | sí (E2E) | [Propuesto] |
| REQ-LIMS-80 | HU-LIMS-22 | EL SISTEMA DEBE ofrecer en la barra lateral: agrupar por solicitud, técnico o cliente; filtro por estado, «Solo atrasados» y técnico (con su carga); búsqueda por solicitud, muestra o ensayo; y zoom Semana, 6 semanas o Trimestre con «Hoy». | sí (E2E) | [Propuesto] |
| REQ-LIMS-81 | HU-LIMS-22 | CUANDO el usuario haga clic en una línea, EL SISTEMA DEBE abrir una ficha con solicitud, cliente, muestra, fechas, técnico, estado, avance y un enlace a «Resultados de la solicitud». | sí (E2E) | [Propuesto] |
| REQ-LIMS-82 | HU-LIMS-22 | EL SISTEMA DEBE seguir mostrando a un técnico sin `ensayos.ver_todos` solo sus líneas, y el cliente según la regla vigente. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-83 | HU-LIMS-22 | EL SISTEMA DEBE mostrar las actividades del calendario en la vista «Actividades» con el mismo diseño, agrupadas por calendario y con su color. | revisión visual | [Decisión Gerente] |
| REQ-LIMS-84 | HU-LIMS-22 | DONDE la pantalla mida menos de 900 px, EL SISTEMA DEBE mostrar cada solicitud como tarjeta con una franja de tiempo por línea. | revisión visual | [Propuesto] |
| REQ-LIMS-85 | HU-LIMS-23 | EL SISTEMA DEBE dibujar los gráficos del dashboard y de Análisis con un tema común (`static/js/graficos_tema.js`): misma paleta validada, tipografía, rejilla, barras redondeadas y ficha emergente, con colores propios del modo oscuro que se actualizan al cambiar el tema. | sí (E2E) | [Decisión Gerente] DP-04 |
| REQ-LIMS-86 | HU-LIMS-23 | EL SISTEMA DEBE mostrar en las cifras del dashboard de cotizaciones, tasa de aceptación e informes un minigráfico de los meses del periodo. | sí (unitaria) | [Propuesto] |

## 2g. Programa de ensayos del día y pestañas del panel (v8)

Origen: reunión del Gerente con el PM sobre el ensayo de rotura (pedido de Frank)
y su respuesta del 2026-11-24 en el hilo «Terminar el proyecto»: «la opción A …
y en proyectos … tabs para muestras, los que estén en ensayos, informes etc. y por
fecha». HU-LIMS-24: *como supervisor de ensayos quiero entregar una hoja por
cliente y por día con todas las probetas que tocan romper, sin importar su edad,
para que los técnicos las ubiquen en las pozas, las midan todas y las rompan*.
HU-LIMS-25: *como jefe de laboratorio quiero ver los proyectos separados por etapa
y por fecha, para que el panel no se vea lleno*.

| ID | Regla |
|---|---|
| RN-12 | Fecha prevista de ensayo de una probeta = fecha de moldeo + edad de ensayo (FOR-004); si falta alguna, `RecepcionMuestra.fecha_ensayo_programado`; si falta también, «sin fecha». Una probeta terminada cuenta el día en que se ensayó (`ResultadoEnsayo.fecha_ensayo`). [Propuesto] |
| RN-13 | En el programa de **hoy** se agregan, marcadas como atrasadas, las probetas pendientes cuya fecha prevista ya pasó. [Propuesto] |
| RN-14 | Cada proyecto cae en una sola pestaña según su acción más urgente (RN-11): registrar o asignar → Muestras; seguir en ensayo → En ensayo; revisar y emitir → Por emitir informe; ver informes → Con informe. Sin cotización → Muestras. [Propuesto] |
| RN-15 | El filtro del panel de proyectos es por **movimiento**: un proyecto «se manejó» en una fecha si ese día se creó o editó, llegaron muestras (recepción), se pidió un ensayo (solicitud), se registró un resultado o se emitió un informe. Por defecto es «Hoy»; también «Todas las fechas» y un rango propio. Semana, semana anterior y mes se agregan después. [Decisión Gerente: hoy por defecto; definición de movimiento: Propuesto] |

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-87 | HU-LIMS-24 | CUANDO un usuario con `ensayos.ver` abra el programa del día, EL SISTEMA DEBE listar las probetas de compresión cuya fecha (RN-12) sea la elegida, aunque vengan de varias recepciones y solicitudes. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-88 | HU-LIMS-24 | EL SISTEMA DEBE agrupar el programa en una hoja por cliente, con el total de probetas, las rotas, las edades y las solicitudes de origen. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-89 | HU-LIMS-24 | SI el usuario no ve todos los ensayos, ENTONCES EL SISTEMA DEBE mostrarle solo sus probetas y el código confidencial del cliente en lugar de su nombre. | sí (unitaria) | [Propuesto] |
| REQ-LIMS-90 | HU-LIMS-24 | MIENTRAS el programa sea el de hoy, EL SISTEMA DEBE incluir las atrasadas (RN-13) y avisar cuántas probetas pendientes no tienen fecha. | sí (unitaria) | [Propuesto] |
| REQ-LIMS-91 | HU-LIMS-24 | CUANDO el usuario abra la hoja de un cliente, EL SISTEMA DEBE mostrar por probeta código de laboratorio, ID del cliente, elemento, f'c, moldeo, edad, solicitud, técnico y estado, y permitir imprimirla. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-92 | HU-LIMS-24 | CUANDO el técnico pulse «Medir y pesar todas primero» en la hoja, EL SISTEMA DEBE guardar masa, D1-D2 y L1-L3 de todas sus probetas pendientes en un solo formulario, aunque sean de solicitudes distintas. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-93 | HU-LIMS-24 | CUANDO el técnico abra una probeta desde la hoja, EL SISTEMA DEBE seguir el registro ya validado (datos del cliente → medidas → fotos en prensa → carga y foto de la carga → probeta rota) y volver a la hoja al salir o terminar. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-94 | HU-LIMS-24 | SI se corrige una medida ya guardada desde la hoja, ENTONCES EL SISTEMA DEBE anotarla en la trazabilidad (`CambioResultado`). | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-95 | HU-LIMS-24 | EL SISTEMA DEBE mantener cada probeta en su solicitud y su informe; la hoja muestra a quien aprueba el acceso a la revisión de cada solicitud finalizada. | sí (revisión) | [Propuesto] |
| REQ-LIMS-96 | HU-LIMS-24 | EL SISTEMA DEBE ofrecer el programa del día en el menú «Laboratorio» y en el menú del celular. | sí (revisión visual) | [Propuesto] |
| REQ-LIMS-97 | HU-LIMS-25 | EL SISTEMA DEBE mostrar en el panel de proyectos las pestañas Todos, Muestras, En ensayo, Por emitir informe y Con informe, cada una con su cantidad (RN-14). | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-98 | HU-LIMS-25 | CUANDO el usuario elija una pestaña, EL SISTEMA DEBE mostrar solo los proyectos de esa etapa, paginados. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-99 | HU-LIMS-25 | CUANDO el usuario abra el panel de proyectos sin filtros, EL SISTEMA DEBE mostrar los proyectos con movimiento hoy (RN-15); CUANDO elija «Todas las fechas» o un rango, EL SISTEMA DEBE filtrar por movimiento en ese rango y recalcular las cantidades de las pestañas. | sí (unitaria) | [Decisión Gerente] |
| REQ-LIMS-100 | HU-LIMS-25 | EL SISTEMA DEBE conservar pestaña, periodo y búsqueda al cambiar de página, de pestaña o al buscar en vivo. | sí (unitaria + revisión) | [Propuesto] |
| REQ-LIMS-101 | HU-LIMS-25 | SI ningún proyecto cumple los filtros, ENTONCES EL SISTEMA DEBE decirlo («Ningún proyecto con movimiento hoy» cuando el filtro es Hoy) y ofrecer «Ver todas las fechas». | sí (unitaria) | [Propuesto] |
| REQ-LIMS-102 | HU-LIMS-25 | DONDE la pantalla mida menos de 768 px, EL SISTEMA DEBE desplazar las pestañas en horizontal sin desbordar la página. | sí (revisión visual) | [Propuesto] |


## 2h. Guardado automático del registro de ensayo (v9)

Origen: conversación del Gerente con Frank (Supervisor de Laboratorio) del
2026-11-25: los técnicos ensayan desde el teléfono o la tablet y, si se acaba la
batería o se cierra el navegador, «esos datos no se tienen que perder»; al
volver a entrar deben poder «continuar el ensayo». El Gerente respondió que cada
dato se guardaba solo; la revisión del 2026-11-25 mostró que solo las fotos lo
hacían, y esta sección lo completa. HU-LIMS-26: *como técnico quiero que lo que
escribo se guarde solo, para no perder el registro si se apaga el teléfono*.

Decisión de Frank sobre el informe, misma conversación: «cada solicitud tiene un
informe» (cierra la pregunta abierta 2 de §4: el informe sigue siendo por solicitud).

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-103 | HU-LIMS-26 | CUANDO el técnico salga de un campo del registro de un ensayo, EL SISTEMA DEBE guardar lo escrito sin pulsar «Guardar», sin terminar el ensayo y sin pedir sesión de ensayo. | sí (unitaria + navegador) | [Validado con usuario] |
| REQ-LIMS-104 | HU-LIMS-26 | SI un dato escrito no es válido, ENTONCES EL SISTEMA DEBE saltarlo, conservar lo ya guardado, guardar el resto y avisar «No se guardó: …». | sí (unitaria) | [Propuesto] |
| REQ-LIMS-105 | HU-LIMS-26 | CUANDO el técnico vuelva a abrir el ensayo, EL SISTEMA DEBE mostrar lo guardado automáticamente. | sí (unitaria + navegador) | [Validado con usuario] |
| REQ-LIMS-106 | HU-LIMS-26 | CUANDO el guardado automático cambie un dato que ya estaba guardado, EL SISTEMA DEBE anotar la corrección en la trazabilidad; el primer guardado de un dato no es una corrección. | sí (unitaria) | [Propuesto] |
| REQ-LIMS-107 | HU-LIMS-26 | MIENTRAS un ensayo tenga datos guardados y no esté terminado, EL SISTEMA DEBE marcarlo «En curso · Continuar» y ofrecer «Continuar» arriba de Mis ensayos. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-108 | HU-LIMS-26 | CUANDO el técnico salga de un campo de «Medir y pesar todas», EL SISTEMA DEBE guardar las medidas de esa pantalla sin crear resultados vacíos ni tocar los terminados. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-109 | HU-LIMS-26 | SI no hay conexión, ENTONCES EL SISTEMA DEBE mantener lo escrito en la pantalla, avisar «Sin conexión» y reintentar el guardado al volver la señal y al cambiar de aplicación. | sí (navegador) | [Propuesto] |
| REQ-LIMS-110 | HU-LIMS-26 | SI el ensayo ya está terminado o la línea no es del técnico, ENTONCES EL SISTEMA DEBE rechazar el guardado automático (409 o 404). | sí (unitaria) | [Propuesto] |


## 2i. Borrador local de formularios largos (v10)

Origen: pedido del Gerente del 2026-11-25 («esto se puede implementar para
cotización y varios procesos críticos; analiza cuáles son críticos y hagámoslo
para muestras, informes, etc.»). Análisis: son críticos los formularios que se
arman en varios minutos y cuya pérdida cuesta trabajo del cliente en el mostrador
o del área comercial: **cotización**, **recepción de muestras**, **solicitud de
ensayo** y **datos de probetas (FOR-004)**. El registro de ensayo ya guarda en
el servidor (HU-LIMS-26) y el editor del informe ya tiene autoguardado y
versiones. No se guarda en el servidor porque una cotización a medias gastaría
un número de oferta y aparecería en las listas. HU-LIMS-27: *como usuario quiero
recuperar lo que estaba escribiendo si se cierra el navegador o se apaga el
equipo, para no volver a capturarlo*.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-111 | HU-LIMS-27 | CUANDO el usuario escriba en el formulario de cotización, EL SISTEMA DEBE guardar un borrador en ese equipo y, al volver a abrir la pantalla, ofrecer «Restaurar borrador» o «Descartar»; la restauración incluye el detalle de ítems y las condiciones. | sí (unitaria + navegador) | [Validado con usuario] |
| REQ-LIMS-112 | HU-LIMS-27 | EL SISTEMA DEBE ofrecer lo mismo en la recepción de muestras, incluidas las filas de muestras ya añadidas. | sí (unitaria + navegador) | [Validado con usuario] |
| REQ-LIMS-113 | HU-LIMS-27 | EL SISTEMA DEBE ofrecer lo mismo en la solicitud de ensayo, incluidas las filas de ensayos e incidencias. | sí (unitaria + navegador) | [Validado con usuario] |
| REQ-LIMS-114 | HU-LIMS-27 | EL SISTEMA DEBE ofrecer lo mismo en los datos de probetas de una recepción. | sí (unitaria + navegador) | [Validado con usuario] |
| REQ-LIMS-115 | HU-LIMS-27 | EL SISTEMA DEBE guardar el borrador solo en el equipo del usuario (por usuario y por pantalla), sin crear registros ni consumir números de oferta. | sí (unitaria) | [Propuesto] |
| REQ-LIMS-116 | HU-LIMS-27 | CUANDO el formulario se guarde bien, EL SISTEMA DEBE borrar el borrador; SI el servidor rechaza el envío por un dato inválido, ENTONCES EL SISTEMA DEBE conservarlo. | sí (navegador) | [Propuesto] |
| REQ-LIMS-117 | HU-LIMS-27 | EL SISTEMA DEBE descartar los borradores de más de 7 días y no ofrecer uno que sea igual a lo que ya muestra la pantalla. | sí (navegador) | [Propuesto] |


## 2j. Plantillas de cotización con el diseño de la cotización (v11)

Origen: pedido del Gerente del 2026-11-25: las plantillas tienen lo mismo que las
cotizaciones pero con un diseño antiguo; deben quedar como la cotización, sobre
todo en servicios, detalle y contenido. Pantallas: `/servicios/plantillas/crear/`
y `/servicios/plantillas/editar/<id>/`. HU-LIMS-28: *como comercial quiero armar
una plantilla con la misma pantalla que una cotización, para no aprender dos
formas de hacer lo mismo*. La plantilla ya compartía `cotizacion-config.js`; lo
que cambia es la pantalla (estilos y modal comunes en `servicios/includes/`).

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-118 | HU-LIMS-28 | EL SISTEMA DEBE mostrar los pasos de la plantilla (General, Servicios, Contenido) como pills redondeadas con su número, igual que la cotización. | sí (unitaria + revisión visual) | [Decisión Gerente] |
| REQ-LIMS-119 | HU-LIMS-28 | MIENTRAS el detalle de la plantilla no tenga ítems, EL SISTEMA DEBE mostrar en el paso Servicios un estado vacío con un solo botón «Agregar detalle»; CUANDO se pulse, EL SISTEMA DEBE abrir el mismo modal a pantalla completa de la cotización (formulario a la izquierda, tabla a la derecha). | sí (navegador) | [Decisión Gerente] |
| REQ-LIMS-120 | HU-LIMS-28 | EL SISTEMA DEBE permitir en la plantilla agregar, editar, subir, bajar y quitar categorías, sub-categorías y servicios con los mismos controles que la cotización, incluida la norma de ensayo. | sí (navegador) | [Decisión Gerente] |
| REQ-LIMS-121 | HU-LIMS-28 | EL SISTEMA DEBE mostrar el paso Contenido con el mismo editor que la cotización (secciones, grupos, datos a completar resaltados en amarillo). | sí (navegador) | [Decisión Gerente] |
| REQ-LIMS-122 | HU-LIMS-28 | CUANDO se guarde la plantilla, EL SISTEMA DEBE enviarla por fetch y, SI hay un error, ENTONCES EL SISTEMA DEBE avisarlo en la misma pantalla sin perder el detalle ni el contenido escritos. | sí (unitaria + navegador) | [Propuesto] |
| REQ-LIMS-123 | HU-LIMS-28 | EL SISTEMA DEBE guardar la norma y el método de cada ítem de la plantilla por su código, y mostrar al editar las plantillas guardadas antes (norma y método juntos) sin repetir el método. | sí (unitaria) | [Propuesto] |
| REQ-LIMS-124 | HU-LIMS-28 | EL SISTEMA DEBE ofrecer en la plantilla el borrador local de HU-LIMS-27. | sí (unitaria) | [Propuesto] |


## 2k. Panel de cada pantalla siempre visible y panel de proyectos compacto (v12)

Origen: pedido del Gerente del 2026-11-25: el botón «Panel» de las pantallas
esconde el buscador, los filtros y las acciones; el usuario puede no verlo.
Análisis: lo usan **25 pantallas** (13 listas y 12 formularios) y es un solo
componente (`command-header`, CSS en `base_vicafpro.html`, JS en `vicafbase.js`).
En el detalle de una recepción esconde «Ir a Ensayos», «Enviar WhatsApp», «Datos de
probetas» y «Editar recepción». HU-LIMS-29: *como usuario quiero ver siempre el
título, la búsqueda, los filtros y las acciones de la pantalla, sin tener que
descubrir un botón*. Además, el panel de proyectos se ve muy lleno: tarjetas y
pestañas más pequeñas.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-125 | HU-LIMS-29 | EL SISTEMA DEBE mostrar siempre, en las 25 pantallas que lo tenían, el contenido del panel (título, búsqueda, filtros y acciones propias) arriba de la pantalla, sin el botón «Panel» ni la X. | sí (navegador, 25 pantallas) | [Decisión Gerente] |
| REQ-LIMS-126 | HU-LIMS-29 | EL SISTEMA DEBE mantener a la derecha del panel las acciones principales de cada pantalla (Nuevo, Volver, Web, Dashboard). | sí (navegador) | [Decisión Gerente] |
| REQ-LIMS-127 | HU-LIMS-29 | DONDE la pantalla mida menos de 640 px, EL SISTEMA DEBE poner las acciones arriba y el panel debajo, sin desbordar la página. | sí (navegador) | [Propuesto] |
| REQ-LIMS-128 | HU-LIMS-25 | EL SISTEMA DEBE mostrar las tarjetas del panel de proyectos más compactas (hasta 4 por fila en pantalla grande), con botones, círculos de etapa y pestañas más pequeños. | sí (revisión visual) | [Decisión Gerente] |


## 2l. Barra del panel con diseño unificado (v13)

Origen: pedido del Gerente del 2026-11-25 sobre el panel ya visible: el buscador y
los controles no guardaban proporción con los botones y los botones de la derecha
debían tener un diseño moderno e innovador, igual en todas las pantallas. HU-LIMS-30:
*como usuario quiero que el panel de cada pantalla se vea ordenado y moderno, para
encontrar rápido la búsqueda, los filtros y las acciones*. Cambio solo de diseño
(CSS común en `base_vicafpro.html`, una plantilla por pantalla ajustada donde hacía falta).

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-129 | HU-LIMS-30 | EL SISTEMA DEBE mostrar el panel de cada pantalla como una sola barra con tres zonas: título, controles (búsqueda y filtros) y acciones, separadas por una línea fina. | sí (navegador, 25 pantallas) | [Decisión Gerente] |
| REQ-LIMS-130 | HU-LIMS-30 | EL SISTEMA DEBE dar a la búsqueda, los selectores, el rango de fechas y los botones del panel la misma altura (2,6 rem) y esquinas redondeadas. | sí (revisión visual) | [Decisión Gerente] |
| REQ-LIMS-131 | HU-LIMS-30 | EL SISTEMA DEBE mostrar la acción principal de cada pantalla (Nuevo…) con degradado y brillo, y las acciones secundarias (Volver, Web, Dashboard, Filtrar, Limpiar) claras, ambas con el icono en una pastilla, con efecto al pasar el cursor y al enfocar. | sí (revisión visual) | [Decisión Gerente] |
| REQ-LIMS-132 | HU-LIMS-30 | DONDE se muestren indicadores o varios filtros (informes, cotizaciones, plantillas), EL SISTEMA DEBE ponerlos en una fila propia debajo del título. | sí (revisión visual) | [Propuesto] |
| REQ-LIMS-133 | HU-LIMS-30 | DONDE la pantalla mida menos de 1100 px, EL SISTEMA DEBE poner las acciones debajo de la barra y, menos de 640 px, a todo el ancho, sin desbordar la página; EL SISTEMA DEBE mantener el mismo diseño en el tema oscuro. | sí (navegador) | [Propuesto] |


## 2m. Nueva recepción: elegir proyecto y registrar muestras (v14)

Pedido del Gerente (2026-11-25): la elección de proyecto debía ocupar toda la pantalla y
ordenarse por fechas; registrar muestras debía parecerse al detalle de la cotización
(una sola pantalla, menos clics) y la tabla tenía datos que no se veían. HU-LIMS-31:
«Como recepcionista quiero elegir el proyecto y registrar muestras de corrido, para recibir al
cliente sin perder tiempo». Alcance: no cambia el modelo ni el contrato del servidor.
Los datos FOR-004 siguen en su pantalla de probetas [Propuesto: pasarlos al modal si se pide].

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-134 | HU-LIMS-31 | CUANDO se abra «Nueva recepción», EL SISTEMA DEBE mostrar los proyectos abiertos con cotización a todo el ancho, con la barra única del panel (título, búsqueda, orden y «Volver»). | sí | [Validado con usuario] |
| REQ-LIMS-135 | HU-LIMS-31 | EL SISTEMA DEBE ordenar por defecto del más reciente al más antiguo y agrupar por fecha de creación (Hoy, Ayer, Esta semana, Este mes, Anteriores); DONDE se elija otro orden (antiguos, entrega más próxima, cliente, menos muestras), EL SISTEMA DEBE aplicarlo sin grupos y ignorar valores no válidos. | sí | [Propuesto] |
| REQ-LIMS-136 | HU-LIMS-31 | EL SISTEMA DEBE mostrar por proyecto la fecha de creación, la entrega estimada (en rojo si venció) y cuántas muestras y recepciones lleva. | sí | [Propuesto] |
| REQ-LIMS-137 | HU-LIMS-31 | CUANDO la persona pulse «Registrar muestras», EL SISTEMA DEBE abrir una pantalla completa con el formulario a la izquierda y lo ya agregado a la derecha, y permitir agregar con Enter conservando tipo, unidad y cantidad. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-138 | HU-LIMS-31 | EL SISTEMA DEBE permitir elegir el tipo con un clic, crear un tipo nuevo sin recargar la página, y editar, duplicar o quitar una muestra antes de guardar. | sí (navegador) | [Propuesto] |
| REQ-LIMS-139 | HU-LIMS-31 | EL SISTEMA DEBE mostrar en la tabla todas las columnas (n.º, ID, tipo, cantidad con unidad, masa, descripción, observaciones, acción) con el texto completo y sin cortes, y avisar que el ID de laboratorio se asigna al guardar. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-140 | HU-LIMS-31 | MIENTRAS se edite una recepción, EL SISTEMA DEBE mostrar las muestras ya guardadas como solo lectura y no reenviarlas. | sí | [Propuesto] |

## 2n. Solicitud de ensayo en una sola pantalla (v15)

Pedido del Gerente (2026-11-25): «Nuevo ensayo» debía verse proporcionado, moderno y con menos
clics, en una sola pantalla. HU-LIMS-32: «Como jefe de laboratorio quiero armar la solicitud en
una pantalla, para asignar ensayos, técnicos y fechas sin recorrer tres pasos». No cambia el
modelo ni lo que recibe el servidor (se siguen enviando los arreglos `muestra_id[]`, etc.).

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-141 | HU-LIMS-32 | EL SISTEMA DEBE mostrar cotización, fechas, plazo y responsable en una sola fila y, CUANDO se elija la cotización, abrir una pantalla completa de asignación con los ensayos a la izquierda y las incidencias en una columna lateral, con el botón de guardar siempre visible (sin pestañas ni scroll de página). | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-142 | HU-LIMS-32 | EL SISTEMA DEBE listar una fila por ensayo pendiente de la cotización, con su norma y método, y permitir elegir varias muestras a la vez (todas, ninguna o por tipo) y un técnico y una entrega por fila. | sí | [Propuesto] |
| REQ-LIMS-143 | HU-LIMS-32 | CUANDO se guarde, EL SISTEMA DEBE crear una línea de ensayo por cada muestra elegida de cada ensayo completo; SI un ensayo está a medias, ENTONCES EL SISTEMA DEBE avisar cuál y no guardar. | sí | [Propuesto] |
| REQ-LIMS-144 | HU-LIMS-32 | EL SISTEMA DEBE ofrecer «Aplicar a todos» (técnico y entrega) y «Todas las muestras», y poner la entrega programada como fecha de cada ensayo que no tenga una. | sí (navegador) | [Propuesto] |
| REQ-LIMS-145 | HU-LIMS-32 | EL SISTEMA DEBE mostrar lo ya asignado y las incidencias previas como solo lectura, y las incidencias nuevas en una sección plegable opcional. | sí | [Propuesto] |
| REQ-LIMS-146 | HU-LIMS-32 | EL SISTEMA DEBE mostrar la norma y el método vacíos, nunca el texto «None», cuando el servicio no los tiene. | sí | [Validado con usuario] |
| REQ-LIMS-148 | HU-LIMS-32 | EL SISTEMA DEBE mostrar en el modal los ensayos ya asignados, agrupados por ensayo, y permitir cambiar su técnico y entrega o quitar las líneas; SI una línea ya tiene resultado, ENTONCES EL SISTEMA DEBE dejarla sin cambios y avisarlo, tanto en pantalla como en el servidor (solo con permiso de editar). | sí | [Propuesto] |
| REQ-LIMS-149 | HU-LIMS-32 | EL SISTEMA DEBE plegar las incidencias nuevas mostrando una línea resumen, abrir solo una a la vez, abrir la nueva al añadir y abrir la elegida al hacer clic. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-147 | HU-LIMS-32 | DONDE haya un borrador local, EL SISTEMA DEBE restaurar cotización, muestras elegidas, técnicos, fechas e incidencias. | sí (navegador) | [Propuesto] |

## 2o. PDF de la solicitud, resultados y lista de solicitudes (v16)

Pedido del Gerente (2026-11-25), con el formato VCF-LAB-FOR-089 v03 de ejemplo. HU-LIMS-33:
«Como jefe de laboratorio quiero la solicitud impresa en el formato oficial, ver primero lo
pendiente y llegar al siguiente paso con un botón claro».

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-150 | HU-LIMS-33 | EL SISTEMA DEBE imprimir la solicitud de ensayo en el formato VCF-LAB-FOR-089 (A4 horizontal): cabecera con logo, normas y n.° de solicitud; datos generales (cotización, ID de cliente, entrega programada y real); detalle por muestra y ensayo (ID laboratorio, ID cliente, estructura, fechas, edad, f'c, técnico, entrega, indicaciones). | sí (imagen del PDF) | [Validado con usuario] |
| REQ-LIMS-151 | HU-LIMS-33 | EL SISTEMA DEBE incluir en el PDF el reporte de incidencias de la solicitud (detalle, fecha, representante del cliente, responsable del laboratorio y si está autorizada), y la franja de modo de supervisión, técnicos y firmas. | sí | [Validado con usuario] |
| REQ-LIMS-152 | HU-LIMS-33 | EL SISTEMA DEBE ordenar la lista de solicitudes con las pendientes primero, luego las en proceso y al final las finalizadas, y dentro de cada grupo por entrega programada. | sí | [Validado con usuario] |
| REQ-LIMS-153 | HU-LIMS-33 | EL SISTEMA DEBE mostrar en cada fila un botón principal grande y de color según el estado: «Iniciar» en pendientes y «Registrar» en las que están en proceso. | sí | [Validado con usuario] |
| REQ-LIMS-154 | HU-LIMS-33 | EL SISTEMA DEBE mostrar los pasos (Iniciar, Registrar resultados, Revisión, Informe) en una columna a la izquierda de arriba abajo y el contenido a la derecha, y destacar más los botones Registrar y Continuar de cada ensayo. | sí (navegador) | [Validado con usuario] |

## 2p. Hoja de resultados de los ensayos generales (v17)

Pedido del Gerente (2026-11-25): el técnico no podía terminar un ensayo general porque pedía una «hoja de cálculo»
sin explicar qué es; además el registro será sobre todo en celular y tablet. HU-LIMS-34.
La hoja es el respaldo de los datos del ensayo (cálculos del técnico: Excel o PDF) y, con esta versión,
también vale una foto o escaneo del formato en papel ya llenado.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-155 | HU-LIMS-34 | EL SISTEMA DEBE explicar en el registro del ensayo general qué es la hoja de resultados y aceptar como tal un Excel, ODS, CSV, PDF o una foto (JPG, PNG, WEBP, HEIC) de hasta 15 MB. | sí | [Validado con usuario] |
| REQ-LIMS-156 | HU-LIMS-34 | DONDE el registro se haga desde un celular o tablet, EL SISTEMA DEBE ofrecer un botón grande «Foto del formato» que abra la cámara y otro para elegir un archivo, y mostrar el nombre de lo elegido antes de guardar. | sí (navegador) | [Propuesto] |
| REQ-LIMS-157 | HU-LIMS-34 | EL SISTEMA DEBE proponer la fecha de hoy como fecha de ensayo en un ensayo general nuevo y decir con claridad qué falta para terminarlo («hoja de resultados (archivo o foto del formato)»). | sí | [Propuesto] |
| REQ-LIMS-158 | HU-LIMS-34 | [Supuesto: pendiente de decisión del Gerente] La hoja de resultados es obligatoria para terminar cualquier ensayo general. | no verificable hasta decidir | [Supuesto] |

## 2q. Registro de compresión alineado al FOR-009 (v18)

Pedido del Gerente (2026-11-25), con la foto del FOR-009 v09 llenado a mano: el registro debe guardar todo lo que
trae la hoja, con 2 fotos antes, 2 durante la carga y 2 después, y dejar trazabilidad de cada corrección.
HU-LIMS-35. Los campos de la hoja ya estaban cubiertos (REQ-LIMS-11 a 19 y 103 a 110); esta versión agrega lo que faltaba.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-159 | HU-LIMS-35 | EL SISTEMA DEBE pedir 6 fotos por probeta, agrupadas en 2 antes del ensayo, 2 durante la carga (la probeta y el display con la carga máxima) y 2 después (probeta fallada, sola y con pizarra), y no dejar terminar sin las 6. | sí | [Validado con usuario] |
| REQ-LIMS-160 | HU-LIMS-35 | CUANDO el técnico escriba el f'c en MPa, EL SISTEMA DEBE convertirlo y guardarlo en kg/cm² (× 10,1972, a 0,01), y usar esa conversión en el cálculo previo del % de f'c. | sí | [Propuesto] |
| REQ-LIMS-161 | HU-LIMS-35 | CUANDO un dato ya guardado cambie, EL SISTEMA DEBE conservar el valor anterior y el nuevo con quién lo cambió y cuándo, y mostrarlo al técnico en el registro y al supervisor en la revisión (ya implementado en REQ-LIMS-103 a 110; se verifica de nuevo). | sí | [Validado con usuario] |
| REQ-LIMS-162 | HU-LIMS-35 | [Supuesto: pendiente] La edad del testigo en horas y la foto aparte de defectos del testigo (FOR-009) se agregan cuando el Gerente confirme que se usan. | no verificable hasta decidir | [Supuesto] |

## 2r. Registro único de resultados para todos los ensayos (v19)

Pedido del Gerente (2026-11-25): compresión es solo un ejemplo; el formulario de resultados es uno solo para todos los
ensayos de cada muestra (marco del FOR-009), en PC, tablet y celular, con 6 fotos por ensayo y sin subir hojas ni imágenes de
resultados. HU-LIMS-36. El bloque «Resultados de ensayo» lo define cada servicio (compresión usa el del FOR-009;
los demás, los campos de su formato en papel [Supuesto: pendiente de recibir cada formato]).

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-163 | HU-LIMS-36 | EL SISTEMA DEBE registrar los resultados de todo ensayo en una sola pantalla, abierta con el botón «Registrar» de su línea en la lista de ensayos de la solicitud. | sí | [Validado con usuario] |
| REQ-LIMS-164 | HU-LIMS-36 | EL SISTEMA DEBE pedir 6 fotos por ensayo de cada muestra, también en los generales: 2 antes, 2 durante y 2 después, y no dejar terminar sin ellas. La galería libre se retira (se muestra solo si ya tenía fotos). | sí | [Validado con usuario] |
| REQ-LIMS-165 | HU-LIMS-36 | DONDE la pantalla sea de celular o tablet, EL SISTEMA DEBE mostrar las fotos guiadas en orden antes → durante → después y un botón «Llenar formulario» siempre visible que lleva al formulario, y viceversa; DONDE sea PC, EL SISTEMA DEBE mostrar formulario y fotos lado a lado. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-166 | HU-LIMS-36 | EL SISTEMA DEBE permitir definir por servicio el formulario de resultados (campos de tipo número, texto, fecha, sí/no, cumple/no cumple y selección; unidad, obligatorio, grupo y ayuda) sin programar, desde el administrador. | sí | [Propuesto] |
| REQ-LIMS-167 | HU-LIMS-36 | EL SISTEMA DEBE copiar el formulario del servicio al crear el resultado, de modo que cambiar la plantilla después no altere ensayos ya registrados. | sí | [Propuesto] |
| REQ-LIMS-168 | HU-LIMS-36 | EL SISTEMA DEBE exigir para terminar la fecha, los campos obligatorios del formulario (o el resumen si el servicio no tiene formulario) y las 6 fotos; ya no se pide hoja de cálculo ni imagen de resultados. | sí | [Validado con usuario] |
| REQ-LIMS-169 | HU-LIMS-36 | CUANDO se corrija un campo del formulario ya guardado, EL SISTEMA DEBE guardar el valor anterior y el nuevo, quién lo cambió y cuándo, y mostrarlo en el registro y en la revisión. | sí | [Validado con usuario] |
| REQ-LIMS-170 | HU-LIMS-36 | EL SISTEMA DEBE mostrar lo registrado en el formulario en la revisión del supervisor y en el bloque de resultados del informe. | sí | [Propuesto] |

## 2s. Formulario completo y fotos guiadas para cualquier dispositivo (v20)

Pedido del Gerente (2026-11-25): el formulario debe ser completo (FOR-009) para todos los ensayos, y llenarse o marcarse
según corresponda (lo que no aplica queda vacío); las fotos deben subirse con una sola cámara o adjuntador que indique cuál
foto sigue, sin perder la secuencia al ir y venir entre datos y fotos, y ocupando poco espacio. HU-LIMS-37.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-171 | HU-LIMS-37 | EL SISTEMA DEBE mostrar en todo ensayo el formulario completo del FOR-009 (datos del cliente, sesión, medidas, verificaciones, defectos, carga, fractura, video y observaciones) y guardarlo, más los campos propios del servicio. | sí | [Validado con usuario] |
| REQ-LIMS-172 | HU-LIMS-37 | DONDE el ensayo no sea de compresión, EL SISTEMA DEBE dejar opcional todo el FOR-009 y exigir para terminar solo la fecha, las 6 fotos y los campos que el servicio marque como obligatorios. | sí | [Propuesto] |
| REQ-LIMS-173 | HU-LIMS-37 | EL SISTEMA DEBE ofrecer un solo control de fotos que indique cuál sigue («Toma/Carga la foto: Antes del ensayo · foto 1 de 6»): «Tomar foto» con la cámara y «Elegir de la galería» en celular y tablet; «Cargar fotos» (varias a la vez, en orden) y la cámara del equipo en PC. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-174 | HU-LIMS-37 | EL SISTEMA DEBE mostrar las fotos en tres grupos plegables (antes, durante y después) con su cuenta y miniaturas, y retomar la secuencia donde quedó al volver de llenar el formulario. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-175 | HU-LIMS-37 | EL SISTEMA DEBE guardar a medida que se llena (guardado automático) y no perder lo escrito al cambiar entre «Fotos» y «Llenar formulario». | sí | [Validado con usuario] |

## 2t. Registro en pantalla completa con la sesión integrada (v21)

Pedido del Gerente (2026-11-25): la sesión de ensayo (condiciones ambientales, equipos y comprobación) forma parte del mismo
formulario FOR-009 y no debe ser otra pantalla; el registro debe ocupar toda la pantalla en columnas para no hacer scroll
largo; las fotos no llevan botones por recuadro (llegan como requisitos) y el sistema dice antes de empezar qué hace falta.
HU-LIMS-38. La sesión sigue siendo necesaria en compresión (trazabilidad de equipos, ISO 17025) y opcional en los demás ensayos.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-176 | HU-LIMS-38 | EL SISTEMA DEBE mostrar el registro del ensayo a pantalla completa, con el formulario en varias columnas, las fotos en un panel lateral y una barra superior con la muestra, el ensayo y el cierre. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-177 | HU-LIMS-38 | MIENTRAS no haya una sesión abierta, EL SISTEMA DEBE mostrar dentro del registro las condiciones iniciales, los equipos y la comprobación funcional, y abrir la sesión sin salir de la pantalla (SI hay errores, ENTONCES EL SISTEMA DEBE mostrarlos sin perder lo escrito). | sí | [Validado con usuario] |
| REQ-LIMS-178 | HU-LIMS-38 | DONDE el ensayo sea de compresión, EL SISTEMA DEBE exigir la sesión abierta para terminar; DONDE no lo sea, EL SISTEMA DEBE dejarla opcional. | sí | [Propuesto] |
| REQ-LIMS-179 | HU-LIMS-38 | EL SISTEMA DEBE mostrar al empezar y mientras se llena una lista de requisitos para terminar (fecha, sesión, medidas, fractura y verificaciones, datos del servicio y fotos, con su avance) que cambia de estado al cumplirse. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-180 | HU-LIMS-38 | EL SISTEMA DEBE quitar los botones de cámara y galería de cada recuadro de foto; para cambiar una foto ya subida, EL SISTEMA DEBE ofrecer «Repetir esta foto», que usa el mismo control guiado. | sí | [Validado con usuario] |

## 2u. Formulario en modal y resumen junto a las fotos (v22)

Pedido del Gerente (2026-11-26): al 100 % de zoom las tarjetas del formulario no caben; el formulario debe abrirse en un modal
a pantalla completa desde un botón «Llenar formulario» (en cualquier dispositivo) y, al pulsar «Listo», lo llenado debe quedar
resumido junto a las fotos, con «Editar formulario» para completar o corregir. El código del cliente viene de la cotización y
no se edita. HU-LIMS-39.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-181 | HU-LIMS-39 | CUANDO la persona pulse «Llenar formulario» (o «Editar formulario»), EL SISTEMA DEBE abrir el formulario completo en un modal a pantalla completa, con las secciones repartidas en columnas según el ancho, sin perder lo ya escrito. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-182 | HU-LIMS-39 | CUANDO se cierre el modal con «Listo», EL SISTEMA DEBE guardar lo escrito y mostrar un resumen de los datos llenados (cliente y probeta, condiciones y equipos, medidas, rotura y verificaciones, resultado preliminar, datos del servicio) en el panel junto a las fotos. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-183 | HU-LIMS-39 | DONDE el ensayo no sea de compresión, EL SISTEMA DEBE resumir solo lo llenado; DONDE sea de compresión, EL SISTEMA DEBE mostrar todas las filas para ver qué falta. | sí | [Propuesto] |
| REQ-LIMS-184 | HU-LIMS-39 | EL SISTEMA DEBE tomar el código del cliente de la cotización (cliente de la solicitud), mostrarlo en el formulario y el resumen como solo lectura y no permitir editarlo; la identificación de cada muestra que da el cliente sigue siendo editable y se rotula «ID de la muestra (del cliente)». | sí | [Validado con usuario] |
| REQ-LIMS-185 | HU-LIMS-39 | DONDE el dispositivo sea celular o tablet, EL SISTEMA DEBE mostrar primero las fotos guiadas y un botón «Llenar formulario» siempre visible. | sí (navegador) | [Validado con usuario] |

## 2v. Modal sobre todo el sistema, video, equipos y fotos tipo escáner (v23)

Pedido del Gerente (2026-11-26): el modal debe cubrir todo el sistema como el detalle de la cotización, con una distribución
compacta que no obligue a hacer scroll; Guardar y Terminar bajo las fotos; ID de laboratorio ya conocido; la casilla de video debe
habilitar su subida; en la sesión, un «+» para registrar equipos sin cambiar de pantalla; las fotos deben centrarse solas como
un escáner (en PC solo se cargan; en celular, cámara y galería) y, en celular y tablet, avisar antes del primer resultado que se
tomen las 2 fotos de antes; el resumen debe verse moderno. HU-LIMS-40.

| ID | HU | Requisito (EARS) | Verificable | Origen |
|---|---|---|---|---|
| REQ-LIMS-186 | HU-LIMS-40 | EL SISTEMA DEBE mostrar el registro y su formulario en pantallas que cubran todo el sistema (por encima de la barra superior y el menú), con el formulario repartido en columnas según el ancho y tipografía y controles compactos, de modo que a 1600 px de ancho quepa sin scroll. | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-187 | HU-LIMS-40 | EL SISTEMA DEBE mostrar los botones Guardar y Terminar debajo del panel de fotos, con el estado del guardado automático y lo que falta. | sí | [Validado con usuario] |
| REQ-LIMS-188 | HU-LIMS-40 | EL SISTEMA DEBE traer el ID de laboratorio de la muestra y mostrarlo como dato fijo en el formulario y el resumen. | sí | [Validado con usuario] |
| REQ-LIMS-189 | HU-LIMS-40 | CUANDO se marque «Se grabó video del ensayo», EL SISTEMA DEBE habilitar la subida del video (MP4, MOV, M4V, WEBM, 3GP o AVI, hasta 300 MB) a la carpeta privada, con barra de avance, descarga solo para quien ve la línea y trazabilidad si se reemplaza. | sí | [Validado con usuario] |
| REQ-LIMS-190 | HU-LIMS-40 | DONDE la persona tenga permiso de editar equipos, EL SISTEMA DEBE mostrar un «+» junto a cada equipo de la sesión que abra un mini-modal para registrarlo y dejarlo elegido sin salir de la pantalla. | sí | [Validado con usuario] |
| REQ-LIMS-191 | HU-LIMS-40 | CUANDO se cargue o tome una foto, EL SISTEMA DEBE detectar el objeto (probeta o display), centrar el encuadre y subirla sin pedir recorte; SI no detecta nada claro, ENTONCES EL SISTEMA DEBE abrir el recorte manual, y siempre ofrecer «Ajustar encuadre». | sí (navegador) | [Validado con usuario] |
| REQ-LIMS-192 | HU-LIMS-40 | DONDE el equipo sea PC, EL SISTEMA DEBE ofrecer solo «Cargar fotos» (varias, en orden); DONDE sea celular o tablet, EL SISTEMA DEBE ofrecer «Tomar foto» y «Elegir de la galería». | sí | [Validado con usuario] |
| REQ-LIMS-193 | HU-LIMS-40 | DONDE sea celular o tablet y falten las 2 fotos de antes, EL SISTEMA DEBE avisar al abrir el formulario por primera vez que se tomen primero, permitiendo continuar sin ellas. | sí | [Validado con usuario] |
| REQ-LIMS-194 | HU-LIMS-40 | EL SISTEMA DEBE mostrar el resumen de lo llenado con un encabezado de resistencia o de datos registrados con su avance y los datos en fichas de color por grupo. | sí (navegador) | [Validado con usuario] |

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
| HU-LIMS-19 | Panel de proyectos con avance por muestra | REQ-LIMS-44 a 52 |
| HU-LIMS-20 | Formulario de cotización con detalle en modal | REQ-LIMS-53 a 61 |
| HU-LIMS-21 | Calendarios de equipo y personales, formulario en dos paneles | REQ-LIMS-62 a 73 |
| HU-LIMS-22 | Gantt de ensayos por solicitud con avance real y atraso | REQ-LIMS-74 a 84 |
| HU-LIMS-23 | Tema común de gráficos (dashboard y Análisis) | REQ-LIMS-85, 86 |
| HU-LIMS-24 | Programa de ensayos del día (hoja por cliente y día) | REQ-LIMS-87 a 96 |
| HU-LIMS-25 | Pestañas por etapa y filtro por fecha del panel | REQ-LIMS-97 a 102, 128 |
| HU-LIMS-26 | Guardado automático del registro de ensayo | REQ-LIMS-103 a 110 |
| HU-LIMS-27 | Borrador local de formularios largos | REQ-LIMS-111 a 117 |
| HU-LIMS-28 | Plantillas con el diseño de la cotización | REQ-LIMS-118 a 124 |
| HU-LIMS-29 | Panel de cada pantalla siempre visible | REQ-LIMS-125 a 127 |
| HU-LIMS-30 | Barra del panel con diseño unificado | REQ-LIMS-129 a 133 |
| HU-LIMS-31 | Nueva recepción: elegir proyecto y registrar muestras | REQ-LIMS-134 a 140 |
| HU-LIMS-32 | Solicitud de ensayo en una sola pantalla | REQ-LIMS-141 a 149 |
| HU-LIMS-33 | PDF de la solicitud FOR-089, resultados y lista | REQ-LIMS-150 a 154 |
| HU-LIMS-34 | Hoja de resultados de los ensayos generales | REQ-LIMS-155 a 158 |
| HU-LIMS-35 | Registro de compresión alineado al FOR-009 | REQ-LIMS-159 a 162 |
| HU-LIMS-36 | Registro único de resultados para todos los ensayos | REQ-LIMS-163 a 170 |
| HU-LIMS-37 | Formulario completo y fotos guiadas para cualquier dispositivo | REQ-LIMS-171 a 175 |
| HU-LIMS-38 | Registro en pantalla completa con la sesión integrada | REQ-LIMS-176 a 180 |
| HU-LIMS-39 | Formulario en modal y resumen junto a las fotos | REQ-LIMS-181 a 185 |
| HU-LIMS-40 | Modal sobre todo, video, equipos y fotos tipo escáner | REQ-LIMS-186 a 194 |

## 4. Preguntas abiertas

| # | Pregunta | Responsable | Estado |
|---|---|---|---|
| 2 | ¿El informe de rotura es uno por solicitud o por hoja del día? | Gerente | Cerrada 2026-11-25: «cada solicitud tiene un informe» (Frank). Queda abierto solo si la solicitud debe pasar a ser por cliente y día. |
| 3 | Numeración de HU: el código de compresión cita HU-LIMS-11 a 20 (CA-20.2) y esta spec usa HU-LIMS-19 y 20 para el panel y la cotización. Confirmar contra `proc/VCF-LIMS_HU_CU_compresion_v2.md`. | PM | Abierta |
| 1 | Al leer `Proyecto.estado` (REQ-LIMS-16) los números pueden diferir del dashboard anterior, que recalculaba la etapa. Comparar en producción antes del pase (PM-02). | Gerente | Abierta |

## 5. Historial

| Versión | Fecha | Autor | Cambio |
|---|---|---|---|
| v0 | 2026-10-12 | DLF | Plantilla inicial |
| v1 | 2026-11-03 | Claude (DLF) | Alcance del dashboard y estados de cotización: RN-01 a 08, REQ-LIMS-01 a 26 |
| v2 | 2026-11-03 | Claude (DLF) | Análisis con tabla dinámica (PR 1): REQ-LIMS-27 a 40 |
| v3 | 2026-11-22 | Claude (DLF) | Panel de proyectos con avance por muestra: RN-09 a 11, REQ-LIMS-44 a 52 |
| v4 | 2026-11-22 | Claude (DLF) | Formulario de cotización: pills y detalle en modal, REQ-LIMS-53 a 59 |
| v5 | 2026-11-22 | Claude (DLF) | Modal del detalle a pantalla completa (formulario a la izquierda, tabla a la derecha): REQ-LIMS-55 a 57 ajustados, 60 y 61 nuevos |
| v6 | 2026-11-24 | Claude (DLF) | Calendario rediseñado: REQ-LIMS-62 a 73 (HU-LIMS-21) |
| v7 | 2026-11-24 | Claude (DLF) | Gantt de ensayos y tema de gráficos: REQ-LIMS-74 a 86 (HU-LIMS-22, 23) |
| v8 | 2026-11-24 | Claude (DLF) | Programa de ensayos del día (RN-12, 13, REQ-LIMS-87 a 96) y pestañas + fecha del panel (RN-14, 15, REQ-LIMS-97 a 102), opción A aprobada por el Gerente |
| v9 | 2026-11-25 | Claude (DLF) | Guardado automático del registro de ensayo: REQ-LIMS-103 a 110 (HU-LIMS-26); informe por solicitud cerrado |
| v10 | 2026-11-25 | Claude (DLF) | Borrador local de cotización, recepción, solicitud de ensayo y datos de probetas: REQ-LIMS-111 a 117 (HU-LIMS-27) |
| v11 | 2026-11-25 | Claude (DLF) | Plantillas de cotización con el diseño de la cotización: REQ-LIMS-118 a 124 (HU-LIMS-28) |
| v12 | 2026-11-25 | Claude (DLF) | Panel siempre visible en 25 pantallas (REQ-LIMS-125 a 127); panel de proyectos compacto (128) y filtro «Hoy» por movimiento (RN-15, REQ-LIMS-99 y 101 ajustados) |
| v13 | 2026-11-25 | Claude (DLF) | Barra única del panel con botones modernos: REQ-LIMS-129 a 133 (HU-LIMS-30) |
| v14 | 2026-11-25 | Claude (DLF) | Nueva recepción: elegir proyecto por fechas y modal «Registrar muestras»: REQ-LIMS-134 a 140 (HU-LIMS-31) |
| v15 | 2026-11-25 | Claude (DLF) | Solicitud de ensayo en una sola pantalla: REQ-LIMS-141 a 149 (HU-LIMS-32) |
| v16 | 2026-11-25 | Claude (DLF) | PDF de la solicitud FOR-089, pasos de resultados a la izquierda, lista por prioridad: REQ-LIMS-150 a 154 (HU-LIMS-33) |
| v17 | 2026-11-25 | Claude (DLF) | Hoja de resultados del ensayo general: foto del formato, botones para celular, fecha de hoy: REQ-LIMS-155 a 158 (HU-LIMS-34) |
| v18 | 2026-11-25 | Claude (DLF) | Registro de compresión alineado al FOR-009: 6 fotos y f'c en MPa: REQ-LIMS-159 a 162 (HU-LIMS-35) |
| v19 | 2026-11-25 | Claude (DLF) | Registro único para todos los ensayos, 6 fotos y formulario por servicio: REQ-LIMS-163 a 170 (HU-LIMS-36) |
| v20 | 2026-11-25 | Claude (DLF) | Formulario FOR-009 completo para todos y asistente de fotos: REQ-LIMS-171 a 175 (HU-LIMS-37) |
| v21 | 2026-11-25 | Claude (DLF) | Registro en pantalla completa con la sesión integrada y requisitos: REQ-LIMS-176 a 180 (HU-LIMS-38) |
| v22 | 2026-11-26 | Claude (DLF) | Formulario en modal, resumen junto a las fotos y código de cliente de la cotización: REQ-LIMS-181 a 185 (HU-LIMS-39) |
| v23 | 2026-11-26 | Claude (DLF) | Modal sobre todo el sistema, video, equipos con «+», fotos tipo escáner y resumen moderno: REQ-LIMS-186 a 194 (HU-LIMS-40) |
