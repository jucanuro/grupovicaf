# Changelog

Cambios notables de **GRUPO VICAF** (LIMS + web institucional).

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

## [Unreleased]

### Added

- `CHANGELOG.md` (este archivo).

### Changed

- En la lista de clientes, la barra de búsqueda del encabezado ahora filtra
  solo esa lista y en vivo mientras se escribe. Antes abría el buscador global
  del sistema y los resultados solo aparecían al presionar ENTER. `Esc` limpia
  el filtro y vuelve a la lista completa.
- La columna Acciones de la lista de clientes tiene un botón "ojo" que abre
  fijada la ficha de detalle (la misma que aparece al pasar el cursor sobre el
  nombre) — útil en pantallas táctiles, donde el hover no existe.

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
