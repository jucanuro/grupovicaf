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
| RN-15 | El filtro por fecha usa `Proyecto.fecha_inicio`: últimos 7, 30 o 90 días, este mes, este año o un rango propio. Por defecto, todas las fechas. [Supuesto] |

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
| REQ-LIMS-99 | HU-LIMS-25 | CUANDO el usuario elija un periodo o un rango de fechas, EL SISTEMA DEBE filtrar los proyectos por su fecha de inicio (RN-15) y recalcular las cantidades de las pestañas. | sí (unitaria) | [Validado con usuario] |
| REQ-LIMS-100 | HU-LIMS-25 | EL SISTEMA DEBE conservar pestaña, periodo y búsqueda al cambiar de página, de pestaña o al buscar en vivo. | sí (unitaria + revisión) | [Propuesto] |
| REQ-LIMS-101 | HU-LIMS-25 | SI ningún proyecto cumple los filtros, ENTONCES EL SISTEMA DEBE decir «Ningún proyecto con estos filtros». | sí (revisión) | [Propuesto] |
| REQ-LIMS-102 | HU-LIMS-25 | DONDE la pantalla mida menos de 768 px, EL SISTEMA DEBE desplazar las pestañas en horizontal sin desbordar la página. | sí (revisión visual) | [Propuesto] |


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
| HU-LIMS-25 | Pestañas por etapa y filtro por fecha del panel | REQ-LIMS-97 a 102 |

## 4. Preguntas abiertas

| # | Pregunta | Responsable | Estado |
|---|---|---|---|
| 2 | ¿El informe de rotura debe seguir siendo uno por solicitud (recepción) o uno por hoja del día (cliente + fecha)? Hoy es por solicitud (REQ-LIMS-70). | Gerente | Abierta |
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
