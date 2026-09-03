# Changelog

Cambios notables de **GRUPO VICAF** (LIMS + web institucional).

---

## [2026-09-03]

### Added

- Módulo común `static/js/form_validador.js` (+ CSS en `base_vicafpro.html`):
  contador de caracteres que aparece al enfocar cada campo, chequeo del contenido
  completo al salir del campo (borde verde / rojo y mensaje debajo), y bloqueo
  del envío con foco en el primer campo inválido. No necesita JS por formulario:
  cada campo se activa con `data-validar` en el input y un
  `<div class="campo-estado" data-for="…">` debajo. Los campos obligatorios
  llevan un asterisco rojo en la etiqueta.
- Ese módulo se aplicó a los formularios de: cliente
  (`clientes/clientes_form.html`), trabajador, rol, norma, método, servicio,
  recepción de muestras, cotización y plantilla de cotización; y a los modales
  de alta rápida de categoría, subcategoría, tipo de muestra y cliente. Todos
  los campos de texto ahora llevan `maxlength`, lo que evita el error
  `value too long for type character varying(N)` por la vía del formulario. El
  RUC del cliente (formulario y modal) exige 11 dígitos numéricos.
- El modal de tipo de muestra limitaba la sigla a 10 caracteres cuando la
  columna admite 5; ahora limita a 5.
- Los formularios con pestañas (recepción, cotización, plantilla) vuelven solos
  a la pestaña del primer campo inválido cuando el módulo frena el envío.
- Carpeta `docs/` con notas de desarrollo; primera nota: `docs/form-validador.md`
  (cómo funciona y dónde está aplicado el módulo de validación de formularios).
- En el formulario de cotización, el campo "Buscar Servicio (Ensayo)" tiene un
  botón "+" que abre un modal de alta rápida de servicio (código de facturación,
  nombre, norma, método, unidad y precio). Al guardar, el servicio nuevo se
  selecciona en el buscador y autocompleta norma/método/precio. Endpoint
  `servicios:crear_servicio_ajax`, modal `servicios/modals/servicio_modal.html`.

### Fixed

- El formulario de servicio (`servicios/servicios_form.html`) no mostraba el
  mensaje de error cuando el guardado fallaba en el servidor; ahora lo muestra
  arriba del formulario.
- `servicios/modals/all_modals.html` incluía dos veces el modal de subcategoría
  y dejaba un `|` suelto visible en la página.

## [2026-09-01 - 2026-09-02]

### Added

- `CHANGELOG.md` (este archivo).
- Comando `python manage.py sembrar_demo` (`core`): genera un dataset de
  demostración coherente respetando la cadena de dependencias — 4 roles, 91
  permisos, 10 trabajadores, catálogos, 50 cotizaciones con sus grupos y
  detalles, ~40 proyectos, ~66 recepciones de muestra, ~250 muestras, ~66
  solicitudes de ensayo con sus detalles e incidencias, y 50 actividades de
  calendario. Todo marcado (`COT-DEMO-*`, `PROY-DEMO-*`, `demo.trab*`,
  `origen_modelo='demo'`) y borrable con `--reset`. No genera `InformeFinal`
  (requiere un PDF por informe).

### Changed

- En la lista de clientes, la barra de búsqueda del encabezado ahora filtra
  solo esa lista y en vivo mientras se escribe. Antes abría el buscador global
  del sistema y los resultados solo aparecían al presionar ENTER. `Esc` limpia
  el filtro y vuelve a la lista completa.
- La columna Acciones de la lista de clientes tiene un botón "ojo" que abre
  fijada la ficha de detalle (la misma que aparece al pasar el cursor sobre el
  nombre) — útil en pantallas táctiles, donde el hover no existe.
- La barra de búsqueda del encabezado (`cabecera_base.html`) es ahora un filtro
  acotado a la lista de cada página: aparece cuando la vista pasa
  `header_search = {'id', 'placeholder'}`, y filtra en vivo mientras se escribe
  (server-rendered, `Esc` limpia, arrastra los filtros del `<form>` si el input
  está dentro de uno). Motor común en `static/js/lista_buscador.js`, activado
  por `[data-lista-buscador]` en el input y
  `[data-lista-contenedor][data-lista-url]` en la plantilla.
- Las 14 listas del LIMS usan ese buscador en el encabezado: clientes,
  servicios, cotizaciones, métodos, normas, plantillas, proyectos pendientes,
  recepciones, solicitudes de ensayo, informes, trabajadores, roles y permisos.
  Cada `<tbody>` sigue siendo HTML de Django (una sola fuente); el JS extrae el
  contenedor de la respuesta.
- La lista de clientes además devuelve solo el parcial de la tabla
  (`clientes/includes/clientes_tabla.html`) en peticiones AJAX — optimización de
  payload opcional que el resto puede adoptar sin cambiar el JS.

### Removed

- Buscador global de comandos (`⌘K` / `#cmd-palette`): la plantilla
  `buscador.html`, su modal, el atajo de teclado y todo su JS en `vicafbase.js`.
  Solo filtraba 5 enlaces fijos, nunca consultaba la base de datos.
- Endpoints de búsqueda por JSON que solo usaban sus propias listas y quedaron
  sin uso: `buscar_servicios_api` y `buscar_trabajadores_api` ya no se invocan
  desde las plantillas (se pueden borrar junto con `buscar_clientes_api` y
  `buscar_cotizaciones_api`, que nunca se usaron).

### Fixed

- La búsqueda de la lista general de recepciones de muestra tiraba `FieldError`
  (`cotizacion__cliente__nombre`, campo inexistente); ahora filtra por
  `razon_social` / procedencia / responsable.

---

## [2026-08-27 – 2026-09-01] — Celery, despliegue y rediseño de la web pública

### Added

- Celery `worker` + `beat`: estampado de QR y notificación del `InformeFinal`,
  correos del formulario de contacto, y barrido diario (07:30 America/Lima) de
  proyectos con fecha de entrega vencida.
- Paquete de despliegue `deploy/`: servicios `systemd` (`vicaflab`, `vicafweb`,
  `vicafworker`, `vicafbeat`), config de `nginx`, backups automáticos
  (`vicafbackup.timer`, retención 7 días) y comandos de exportación /
  revinculación de contenido web (`exportar_datos_web`,
  `cargar_servicios_publicados`, `revincular_catalogo`).
- `SITE_NOINDEX`: bandera global que fuerza `noindex,nofollow` y `robots.txt`
  `Disallow: /` en el rol `web` mientras el contenido no esté redactado.

### Changed

- Home rediseñada: hero replicado de vicafpro, footer, servicios por línea con
  galerías, sección "Nosotros".
- Cobertura acotada a Cajamarca; ubicación en el home; paleta de color unificada.
- `Servicio.nombre` ampliado de 150 a 255 caracteres (un registro real lo
  desbordaba).

### Fixed

- Arranque de los servicios `systemd`.

## [2026-08-23] — Capa web pública y contenedores

### Added

- **Segundo sitio desde el mismo código**: `SITE_ROLE` (`lab` | `web`) elige
  `urls_lab.py` o `urls_web.py`; dos procesos gunicorn separados, misma base de
  datos.
- Apps `web_*` (contenido público, sin duplicar modelos del LIMS): `web_inicio`,
  `web_nosotros`, `web_acreditacion`, `web_catalogo` (publica servicios /
  clientes / equipo con lista blanca de campos), `web_zonas`, `web_contacto`
  (mensajes y solicitud de cotización pública).
- App `siteconfig`: `NegocioConfig` (NAP) y `SeoModel` base (slug, meta_title,
  meta_description, noindex, imagen_og).
- SEO: JSON-LD por tipo (`LocalBusiness`, `Service`, `FAQPage`,
  `BreadcrumbList`), canonical absoluto con `SITE_URL`, `sitemaps`.
- Infraestructura: `Dockerfile` multi-stage, `docker-compose.yml` (prod) y
  `docker-compose.dev.yml` (dev), settings partidos en
  `base` / `dev` / `prod` / `test_local`, PostgreSQL 16, Redis 7.
- Cookies de sesión y CSRF aisladas por rol (`gv_lab_*` / `gv_web_*`).

## [2025-10-21 – 2026-06] — Núcleo del LIMS

### Added

- Apps del laboratorio:
  - `core` — login (`CoreLoginView`), dashboard con analítica del negocio.
  - `clientes` — `Cliente` (RUC, razón social, código confidencial, logo, firma).
  - `trabajadores` — `TrabajadorProfile`, roles y permisos por módulo.
  - `servicios` — `Norma`, `Metodo`, `Servicio`, cotizaciones, vouchers.
  - `proyectos` — `Proyecto`, recepción de muestras, solicitudes de ensayo,
    incidencias, `InformeFinal`, vistas Gantt y calendario.
  - `actividades` — ejecución de ensayos y registro de resultados.
- Generación de PDF (WeasyPrint / xhtml2pdf / reportlab): cotizaciones, cargo de
  muestra, informes de ensayo.
- Flujo de cotización completo: creación, aprobación, textos dinámicos, PDF.
- Migración de la base de datos de SQLite a PostgreSQL.

---

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Todavía no se usan versiones SemVer: las entradas se agrupan por fecha. El
detalle commit a commit está en `git log`.

<!--
Al trabajar, agregá una línea bajo la sección que corresponda dentro de
[Unreleased], en el MISMO commit que el cambio:
  Added       funcionalidad nueva
  Changed     cambios en funcionalidad existente
  Deprecated  algo que se va a quitar pronto
  Removed     algo que se quitó
  Fixed       bugs corregidos
  Security    vulnerabilidades tapadas
Si el cambio no se nota desde afuera (refactor interno, rename de variable),
NO va acá: eso vive solo en git log.
Al entregar un bloque de trabajo: renombrá [Unreleased] a una fecha y creá
un [Unreleased] vacío nuevo.
-->
