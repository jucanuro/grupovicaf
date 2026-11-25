# GRUPO VICAF — Contexto del proyecto

## Qué es esto

Proyecto Django único que sirve **dos sitios** desde el mismo código y la misma base de datos:

| Rol | Dominio | `SITE_ROLE` | URLconf |
|---|---|---|---|
| Web institucional pública | `www.grupovicaf.com` | `web` | `grupovicaf/urls_web.py` |
| LIMS (sistema de laboratorio) | `laboratorio.grupovicaf.com` | `lab` | `grupovicaf/urls_lab.py` |
| Correo (módulo del LIMS) | `email.grupovicaf.com` | `lab` | `grupovicaf/urls_correo.py` |

Se ejecutan como **dos procesos gunicorn separados** con distinta variable de entorno
`SITE_ROLE`, para que un informe PDF pesado del laboratorio nunca frene la web pública.

El negocio: laboratorio de ensayo de materiales y geotecnia acreditado por INACAL, con
sede única en Cajamarca. Opera solo en Cajamarca (D-VCF-002): no se crean páginas
ni contenido para otras ciudades.

## Stack

- Django 4.2 · PostgreSQL 16 · Redis 7 · Celery
- Tailwind CSS (`npm run build:css`)
- WeasyPrint / xhtml2pdf / reportlab para informes
- Docker + docker compose (dev y prod)
- Deploy: EC2 única + Nginx + Certbot

## Apps

### Capa LIMS (interna) — NO renombrar, NO romper migraciones

| App | Responsabilidad |
|---|---|
| `core` | Login, dashboard, analítica interna |
| `clientes` | `Cliente` — RUC, razón social, código confidencial, logo, firma |
| `trabajadores` | `TrabajadorProfile`, roles y permisos por módulo |
| `servicios` | Catálogo de ensayos (`Norma`, `Metodo`, `Servicio`), cotizaciones, vouchers |
| `proyectos` | `Proyecto`, recepción de muestras, solicitudes de ensayo, `InformeFinal` |
| `actividades` | Ejecución de ensayos y resultados |
| `correo` | Pantalla de entrada (`/inicio/`) y módulo de correo en `email.` (ver abajo) |

**Correo en su propio host.** `correo.middleware.CorreoHostMiddleware` cambia el
URLconf a `urls_correo.py` cuando el host es `CORREO_HOST` (solo rol `lab`; en
dev `email.localhost:<puerto>`). Las cookies **no** se comparten entre hosts
(regla 5): `laboratorio.` → `email.` usa un enlace firmado de un solo uso
(`correo/enlaces.py`, 60 s). Las cuentas visibles salen siempre de
`correo.cuentas.cuentas_de(user)`; el acceso se revisa en el servidor.

Plataforma (Paso 2): modelos reales en `correo/models.py` (`CuentaCorreo`,
`AccesoCuenta` con rol lectura/gestiona/administra, `Carpeta`, `Hilo`,
`Mensaje`, `Adjunto`, `Firma`, `EventoMensaje` = bitácora, `Asignacion`).
Toda consulta pasa por `correo/cuentas.py` (`exigir_cuenta`, `exigir_mensaje`,
`exigir_hilo`: 404 si la cuenta no es suya, 403 si su rol no alcanza). El HTML
recibido se limpia con nh3 (`correo/sanitizar.py`) y se muestra en un iframe
sandbox sin scripts con CSP propia; las imágenes remotas van bloqueadas. Los
archivos van a `CORREO_ALMACEN_DIR` (privado, nunca MEDIA_ROOT) y se descargan
con enlace firmado de 300 s. El envío es simulado (`ServicioEnvioSimulado`,
cola Celery `correo`; `@falla.invalid` simula un rebote) hasta el Paso 5.
Datos de ejemplo: `python manage.py seed_correo_demo --usuario <username>`
(solo `DEBUG=True`). Quill 2.0.3 está vendorizado en `static/vendor/`.

Correo real en local: `docker-compose.dev.yml` levanta **Mailpit** (bandeja web
http://localhost:8025, SMTP localhost:1025) y pone `CORREO_ENVIO=smtp`. Lo que
se envía sale como MIME real (`correo/envio.py`) hacia Mailpit; lo que llega a
una cuenta VICAF vuelve a su bandeja cada 15 s por `correo/mailpit.py` (beat),
que usa la misma `RecepcionEML` (`correo/recepcion.py`) que tendrá el webhook
de Cloudflare. Comandos: `simular_entrante` (un cliente escribe o responde,
solo DEBUG), `recibir_eml archivo.eml` (correos reales exportados) y
`traer_mailpit`. En producción `CORREO_SMTP_*` apuntará al SMTP de Amazon SES.

Paso 3 (archivos y administración): `CORREO_ALMACEN=local` (dev/pruebas,
carpeta privada) o `r2` (prod: bucket **privado** de Cloudflare R2 vía
django-storages, `CORREO_R2_*` en el `.env`; boto3 solo se importa en ese
modo). Una descarga primero valida el enlace firmado propio y luego redirige
a una URL prefirmada de R2 de `CORREO_URL_FIRMADA_SEGUNDOS` (300 s); las
imágenes del cuerpo (cid:) siguen pasando por Django por la CSP del iframe.
Cuentas y accesos se gestionan en `email.<dominio>/administrar/`
(`correo/administracion.py`): superusuario o permiso `correo.administrar`
crea/activa cuentas (solo dominios `CORREO_DOMINIOS`); el rol «administra»
de una cuenta gestiona sus accesos. Administrar no da lectura. Todo cambio
queda en `EventoCuenta` (bitácora).

Pasos 4 y 5 (correo real): `correo/webhooks.py`. `POST /api/entrante/` en el
host del correo recibe el .eml crudo del Email Worker de Cloudflare
(`deploy/cloudflare/correo-entrante.js`), firmado con HMAC-SHA256 y fecha
(`CORREO_WEBHOOK_SECRET`); rechaza con 404 las cuentas inexistentes, deja el
.eml en el almacén y la tarea `recibir_entrante` lo pasa por `RecepcionEML`
(idempotente). `POST /api/ses/<CORREO_SES_TOKEN>/` recibe de SNS los rebotes
y quejas de SES (`procesar_evento_ses`: rebote permanente = «Falló el envío»).
`CORREO_SES_CONFIG_SET` añade la cabecera de conjunto de configuración. Guía:
`deploy/cloudflare/README.md`.

**Resultados de ensayo (fase 1).** Cada línea de la solicitud
(`DetalleSolicitudEnsayo`) tiene un `ResultadoEnsayo` (antes `EnsayoCompresion`)
con `plantilla`: «compresion» (ASTM C39 / EC001, lo de abajo) o «general»
(fecha, resumen, hoja de cálculo privada en `ENSAYOS_FOTOS_DIR` y una galería
de fotos tipo `general`: mínimo 1, hasta 12, sin recorte, se quitan con
trazabilidad; no pide sesión). «Tomar foto» abre la cámara en la página en la
PC (`static/js/camara_foto.js`, getUserMedia; el `capture` del input solo
sirve en el celular, que sigue usando la cámara nativa). Rutas en `/proyectos/resultados/` (las viejas `/compresion/`
redirigen con 301). El estado de la `SolicitudEnsayo` lo pone
`sincronizar_estado()`: en proceso con el primer resultado, finalizado cuando
todas las líneas terminan; «Finalizar» a mano se bloquea sin todos los
resultados. Quien ejecutó una línea no la devuelve ni la aprueba (ISO 17025).
En la lista de solicitudes, ▶ inicia (pasa a «en proceso») y el icono verde
abre `/proyectos/resultados/solicitud/<id>/` (pantalla completa con los pasos
Iniciar → Registrar resultados → Revisión → Informe y cada ensayo por
registrar); ya no se finaliza a mano. Quien ve todos los ensayos puede pasar el
formato en papel a nombre del técnico asignado: abre su sesión
(`?tecnico=<id>`) y la línea queda «Ejecutado por» el técnico y
`registrado_por` quien la escribió.
El registro de compresión sigue el orden del laboratorio: 1 datos del cliente
(el técnico los copia; `DatosClienteProbetaForm`), 2 medidas y masa, 3 fotos
en la prensa antes de ensayar, 4 carga + resultado preliminar + foto del
display, 5 probeta rota (falla y 2 fotos); orden en `FotoEnsayo.ORDEN_TOMA`.
«Medir y pesar todas primero» (`/resultados/solicitud/<id>/medidas/`) guarda
masa, D y L de todas las probetas de corrido. Trazabilidad: toda corrección de
un dato ya guardado (también datos del cliente y fotos reemplazadas) queda en
`CambioResultado` (`proyectos/trazabilidad.py`) y se ve en la revisión.
Plazo de entrega (oferta VCF-LAB-FOR-001, `proyectos/plazos.py`): probetas 24 h
después del ensayo; sábado/domingo → lunes. Se ve en la pantalla de la
solicitud y en la lista de revisión (vencido en rojo).

**Programa del día (HU-LIMS-21).** El supervisor entrega una hoja por cliente y
por día, no por recepción: `/proyectos/programa/` (`proyectos/programa.py`,
vistas en `views_compresion.py`) junta las probetas de compresión cuya fecha
prevista (moldeo + edad; si no, `RecepcionMuestra.fecha_ensayo_programado`) es
ese día, aunque vengan de varias solicitudes; hoy suma las atrasadas. La hoja
del cliente se imprime, tiene «Medir y pesar todas» (mismo lote que la
solicitud, `_medidas_en_lote`) y cada «Romper» vuelve a la hoja
(`?desde=programa`). El técnico ve el código confidencial del cliente, no su
nombre. Cada probeta sigue en su solicitud e informe. El panel de proyectos
tiene pestañas por etapa (acción más urgente) y filtro por `fecha_inicio`.

**Informe tipo Word (fase 2).** Todo informe, también el de compresión, pasa por el
editor: al aprobar los resultados se abre `/proyectos/resultados/informe/<id>/editor/`
(`views_informe_editor.py`, `informe_editor.py`, permiso `informes.aprobar`).
TipTap 2.27.1 va empaquetado en `static/vendor/tiptap-2.27.1/` (sin CDN). El
`BorradorInforme` guarda el JSON del editor con autoguardado y control de
versión (409 si otra pestaña guardó antes) y un `VersionInforme` cada 10 min o
al cambiar de autor. Los «bloques de datos» (carátula, resultados, fotos,
equipos, firmas) solo guardan tipo y referencia y se dibujan desde la base
(`templates/proyectos/informe_bloques/`); el JSON se valida con lista blanca
antes de guardar y de renderizar. Emitir exige los bloques obligatorios y que
quien firma no haya ejecutado ningún ensayo; congela `html_emitido` y Celery
(`generar_informe_editor`) arma el PDF con WeasyPrint. El texto de los bloques
se puede seleccionar y copiar; con el permiso `informes.editar_datos` (no se da a
ningún rol por defecto) un bloque de carátula, resultados, equipos o notas se
puede «Convertir en texto editable» (nodo `bloqueEditado`): queda en el
historial, ya no se actualiza solo y el servidor rechaza (403) que alguien sin
el permiso lo cree o cambie su texto. El editor se abre a pantalla completa
(como Word: barra arriba, hoja A4 con cortes de página aproximados, barra de
estado con palabras, páginas y zoom); «Salir» vuelve a la vista con el menú.

**Ensayo de compresión (HU-LIMS-14).** `proyectos/views_compresion.py`:
el técnico registra en el celular cada probeta de ASTM C39 / EC001 asignada
(`/proyectos/resultados/`) con 5 fotos obligatorias recortadas con proporción
fija (Cropper.js 1.6.2 vendorizado; carga 18:7, probeta 4:7, en
`FotoEnsayo.PROPORCIONES`). Al abrir el recorte, `static/js/centrado_foto.js`
coloca el marco sobre la probeta o el display (en el celular, sin librerías;
si no encuentra nada claro deja el marco centrado). Sin las 5 fotos y la fecha no se puede terminar.
Las fotos van a `ENSAYOS_FOTOS_DIR` (privado, nunca MEDIA_ROOT; en prod debe
existir, ser escribible por el servicio y entrar en el backup) y se sirven
por una vista con sesión. Permiso `ensayos.registrar`.
Medidas y cálculos (HU-LIMS-11 a 13): recepción llena los datos FOR-004 de
cada probeta (`/proyectos/recepcion/<id>/probetas/`, permiso `muestras.editar`);
el técnico abre una `SesionEnsayo` (T/HR y los 6 equipos con calibración
vigente; `Equipo` en `/proyectos/equipos/`, permisos `equipos.ver`/`equipos.editar`)
y registra masa, D1-D2, L1-L3, carga y fractura. Como en el formato de registro en papel
(versión 09): la sesión también pide anillos retenedores, neoprenos (con n.º de
usos) y la comprobación funcional de equipos (`SesionEnsayo.COMPROBACION`; si un
equipo no pasa, no se abre la sesión), y cada probeta lleva la verificación del
diámetro (calculada, ≤ 2 %), perpendicularidad y planitud (las marca el técnico),
defectos a-e (`tipos_defecto` + texto de «Otros») y si se grabó video. Las reglas de cálculo están en
`proyectos/calculos_compresion.py` (π = 3,1416 como la hoja del laboratorio) y
su copia de vista previa en `static/js/compresion_calculos.js`: si cambia una,
cambiar la otra.
Revisión e informe (HU-LIMS-15 a 19, `views_informe_compresion.py`): quien
tiene `informes.aprobar` devuelve o aprueba en `/proyectos/resultados/revision/`;
al aprobar (todas terminadas y sesiones cerradas) se pasa al editor del informe;
el PDF antiguo (`informe_compresion_pdf.html`, `generar_informe_compresion`)
solo queda para regenerar informes emitidos antes del editor. Excel con openpyxl (`informes.exportar`); envío al cliente con
`enviar_informe_cliente`.

**Oferta técnico-económica (FOR-001 v7).** El PDF de la cotización
(`servicios/oferta_pdf.py` + `templates/servicios/oferta_pdf.html`, WeasyPrint)
copia el Word oficial: marco gris con cuadro naranja, cabecera con logo y
contactos (`static/img/oferta/`), código del formato girado con «Página X de Y»,
tabla de ítems con categorías A/B y subcategorías a/b, notas numeradas,
secciones 2… con grupos, contactos, datos de pago y firmas. Los textos de
condiciones salen del Word a `servicios/seeds/condiciones.py`
(`python cargar_condiciones.py --apply [--solo-word]`): lo resaltado en el Word
que es un dato a completar va entre llaves dobles (amarillo en el formulario, sin
llaves en el PDF); los párrafos resaltados completos son alternativas sin marcar.
Si cambia la versión del Word, actualizar `FORMATO` en `oferta_pdf.py` y el seed.

### Capa web (pública) — prefijo `web_` obligatorio

| App | Responsabilidad |
|---|---|
| `web_inicio` | Carrusel y home |
| `web_nosotros` | Misión, visión, documentos |
| `web_acreditacion` | Acreditación INACAL y alcance |
| `web_catalogo` | Publicación sobre `servicios`, `clientes` y `trabajadores` |
| `web_zonas` | **Descartada** (D-VCF-002): no se crean landing pages por ciudad |
| `web_contacto` | Mensajes y solicitud de cotización pública |
| `web_empleo` | Convocatorias y postulaciones |
| `web_portal` | Portal del cliente + validación pública de informes por QR |

**El prefijo `web_` es obligatorio**: `core`, `clientes`, `trabajadores` y `servicios` ya
existen en la capa LIMS y Django no admite dos apps con el mismo label.

## Reglas no negociables

1. **Nunca duplicar modelos del LIMS.** Las apps `web_*` no definen `Cliente`, `Servicio`
   ni `Trabajador`. Leen los modelos del LIMS y añaden, cuando hace falta, un modelo
   companion con `OneToOneField` (ej. `web_catalogo.ServicioPublicado`).

2. **Lista blanca de campos en toda vista pública.** La BD contiene RUCs, montos,
   vouchers y `codigo_confidencial`. Usar `.only()` / `.values()` con campos explícitos.
   Prohibido pasar un modelo del LIMS completo a una plantilla pública.

3. **Campos prohibidos en cualquier respuesta pública:**
   `Cliente.codigo_confidencial`, `Cliente.ruc`, `Cliente.firma_electronica`,
   `Proyecto.monto_cotizacion`, `Proyecto.codigo_voucher`,
   todo `Cotizacion` salvo la del propio cliente autenticado,
   `TrabajadorProfile.firma_electronica`.

4. **`urls_web.py` no incluye `admin/`.** El admin vive solo en `urls_lab.py`.

5. **Cookies de sesión aisladas** vía `SESSION_COOKIE_NAME = f'gv_{SITE_ROLE}_sessionid'`.

6. **Nada de secretos en el código.** Todo por `.env`. `.env.example` sí se versiona,
   con claves pero sin valores.

7. **Toda tarea de más de ~1 segundo va a Celery**: PDF, QR, correo, SMS.

8. `AUTH_USER_MODEL` es el `auth.User` por defecto. No cambiarlo: `actividades` y
   `proyectos` importan `django.contrib.auth.models.User` en migraciones ya aplicadas.

## Reglas SEO (aplican a toda página pública)

9. **Un H1 por página**, con la keyword objetivo. Nunca cero, nunca dos.

10. **Una keyword principal por URL.** Dos páginas compitiendo por la misma frase se
    canibalizan. Antes de crear una página, verifica que su keyword no esté ya asignada.

11. **Todo modelo con página propia hereda de `SeoModel`** (`grupovicaf/seo.py`):
    slug, meta_title (≤60), meta_description (≤160), noindex, imagen_og.

12. **Canonical absoluto en toda página**, construido con `SITE_URL`.

13. **Datos estructurados JSON-LD** según el tipo: `LocalBusiness` global,
    `Service` en servicios y zonas, `FAQPage` donde haya preguntas frecuentes,
    `BreadcrumbList` en toda página interna, `JobPosting` en convocatorias.

14. **NAP consistente.** Nombre, dirección y teléfono idénticos en JSON-LD, footer y
    página de contacto. Definidos en un solo lugar, nunca hardcodeados por plantilla.

15. **`noindex` obligatorio** en `/portal/`, `/proyectos/v/` y cualquier vista con datos
    de cliente. Excluidas del sitemap.

16. **Nunca generar contenido de zona o servicio por plantilla sustituyendo la ciudad.**
    Eso es una doorway page y Google la penaliza. Dejar placeholder marcado como
    PENDIENTE DE REDACCIÓN y avisar.

17. **Rendimiento es ranking**: `output.css` purgado, imágenes con `width`/`height` y
    `loading="lazy"`, fuentes con `font-display: swap`, sin JS bloqueante en el `<head>`.

18. **Toda URL que cambie necesita un 301** desde la ruta antigua de vicafpro.

## Comandos

### Docker (desarrollo)

Servicios: `db` (Postgres 16), `redis` (Redis 7), `lab` (:8000), `web` (:8001),
`node` (Tailwind en modo watch, se activa en F3).

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml exec lab python manage.py migrate
docker compose -f docker-compose.dev.yml exec lab python manage.py test
docker compose -f docker-compose.dev.yml exec lab python manage.py auditar_seo
docker compose -f docker-compose.dev.yml logs -f lab web
docker compose -f docker-compose.dev.yml down          # conserva el volumen postgres_data
```

Si el puerto 8000 del host ya está ocupado por otro proyecto, fija
`LAB_HOST_PORT=<puerto libre>` en `.env` (el contenedor sigue escuchando en
8000 internamente; solo cambia el mapeo hacia el host).

`db` y `redis` **no publican puertos al host** por defecto: `lab`/`web` los
resuelven por nombre de servicio (`db`, `redis`) dentro de la red de Compose.
Para entrar con un cliente psql/redis-cli desde el host, usa
`docker compose -f docker-compose.dev.yml exec db psql -U grupovicaf`.

`grupovicaf/settings/dev.py` usa Postgres solo si `DB_HOST` está definido en
el entorno (así lo inyecta `docker-compose.dev.yml` vía `.env`); sin Docker,
sigue cayendo a `db.sqlite3` como hasta ahora.

### Pruebas E2E (Playwright)

```bash
E2E_PYTHON=venv/bin/python npm run test:e2e   # levanta lab y web, siembra y prueba
```

Detalle en `e2e/README.md`. Datos fijos con `python manage.py sembrar_e2e`
(solo `DEBUG=True`). Job `e2e` en `.github/workflows/ci.yml`.

### Restaurar/migrar datos al Postgres del contenedor

**Estado: hecho.** `db.sqlite3` (backup, no se borra) ya se migró al Postgres
del contenedor dev. No hay un volcado `.sql` versionado (los
`.sql`/`.gz`/`.zip`/`.dump` están en `.gitignore`). El volcado se acota a las
apps del LIMS — `auth.user`, `clientes`, `trabajadores`, `servicios`,
`proyectos`, `actividades` — porque las apps `web_*` y `siteconfig` traen su
propio seed vía migraciones de datos (`RunPython`) y algunas (`web_nosotros`)
ya tenían contenido propio en Postgres que no viene de `db.sqlite3` y no debe
pisarse:

```bash
# 1. Volcar desde sqlite (fuera de Docker, con DB_HOST vacío para no apuntar a Postgres)
DB_HOST= SITE_ROLE=lab DJANGO_SETTINGS_MODULE=grupovicaf.settings.dev \
  venv/bin/python manage.py dumpdata auth.user clientes trabajadores servicios proyectos actividades \
  --natural-foreign --natural-primary \
  --indent 2 -o db_dump.json

# 2. Con los contenedores arriba y el volumen de código montado en /app:
docker compose -f docker-compose.dev.yml exec lab python manage.py migrate
docker compose -f docker-compose.dev.yml exec lab python manage.py loaddata db_dump.json
rm db_dump.json   # no versionar el volcado
```

`--natural-primary` solo afecta a `auth.User` (el único modelo del volcado
con `natural_key()`); el resto conserva su PK explícita de sqlite, así que
`loaddata` sobreescribe por PK cualquier fila placeholder que ya existiera en
Postgres (p. ej. las `Norma`/`Metodo`/`CategoriaServicio` de prueba creadas a
mano mientras la tabla estaba vacía).

> **Resuelto**: el desborde conocido de `Servicio.objects.get(pk=16).nombre`
> (156 caracteres contra `max_length=150`) ya no existe — el campo se amplió
> a `max_length=255` en un commit posterior. Una auditoría completa de los
> 173 `CharField`/`SlugField` de las 13 apps propias contra los datos reales
> de `db.sqlite3` (2026-08-31) no encontró ningún campo desbordado.

### Restaurar el dump de Postgres en producción (EC2)

Volcado generado con `pg_dump -F c` (formato *custom*, comprimido, admite
`pg_restore --clean` para reemplazar el esquema existente):

```bash
# En el host de producción, con el contenedor db arriba:
docker compose cp grupovicaf_YYYYMMDD.dump db:/tmp/grupovicaf.dump
docker compose exec db pg_restore -U grupovicaf -d grupovicaf --clean --if-exists /tmp/grupovicaf.dump
docker compose exec db rm /tmp/grupovicaf.dump
docker compose exec lab python manage.py migrate   # por si el dump es de una revisión anterior
```

### Actualizar contenido web sin tocar el LIMS

AWS es la fuente de verdad del LIMS (`clientes`, `trabajadores`, `servicios`,
`proyectos`, `actividades`) y **nunca se sobrescribe** desde dev. Cuando lo
que cambió en local es solo contenido web (`web_inicio`, `web_nosotros`,
`web_acreditacion`, `web_catalogo`, `web_contacto`,
`siteconfig`), se sube con este procedimiento en vez de `pg_restore`.

**El problema de fondo**: `LineaServicio.ensayos` (M2M), `Acreditacion.
servicios_acreditados` (M2M) y `ServicioPublicado.servicio` (FK) apuntan a
`servicios.Servicio`. Los IDs de esa tabla NO coinciden entre bases (dev
tiene 99 `Servicio` de prueba, AWS tiene los 14 reales) — subir esos campos
tal cual enlazaría cada línea/ensayo al `Servicio` equivocado. Además,
`ServicioPublicado.categoria` es un FK NOT NULL a `servicios.
CategoriaServicio`, y en dev esa tabla solo tiene categorías placeholder
("Categoria 1", "cATEGORÍA 2"...) sin ningún significado real — no hay nada
que emparejar por nombre ahí, así que el volcado no puede traer esa columna.

**1. En dev, generar el paquete** (no se versiona, ver `.gitignore`):

```bash
docker compose -f docker-compose.dev.yml exec lab python manage.py exportar_datos_web --output-dir /tmp
docker compose -f docker-compose.dev.yml cp lab:/tmp/web_dump.json .
docker compose -f docker-compose.dev.yml cp lab:/tmp/web_dump_relink.json .
```

Produce dos archivos:
- `web_dump.json`: fixture estándar de Django (todo `web_*`/`siteconfig`
  excepto `ServicioPublicado`), con `LineaServicio.ensayos`,
  `Acreditacion.servicios_acreditados`, `ServicioPublicado.servicio`,
  `SolicitudCotizacionWeb.cliente/cotizacion` y `MensajeContacto.
  atendido_por` vacíos.
- `web_dump_relink.json`: lo que depende del catálogo LIMS — cada
  `ServicioPublicado` (con su `servicio` original como snapshot de
  nombre/código, no de ID) y las listas de `Servicio` que cada
  `LineaServicio`/`Acreditacion` tenía vinculadas.

**2. Copiar ambos archivos al host de producción** (`scp`, no por git) y, con
los contenedores arriba:

```bash
docker compose cp web_dump.json lab:/tmp/web_dump.json
docker compose cp web_dump_relink.json lab:/tmp/web_dump_relink.json

# 2a. Recrea ServicioPublicado con su mismo pk y una categoría placeholder
#     explícita ("Sin categorizar (pendiente)") — hay que reasignarla a mano
#     desde el admin después. Sin este paso, el loaddata de 2b falla: NOT
#     NULL en categoria_id apuntando a un modelo que no se sube.
docker compose exec lab python manage.py cargar_servicios_publicados /tmp/web_dump_relink.json

# 2b. Todo lo demás, con PK preservada (PreguntaFrecuente,
#     ZonaCobertura.servicios, SolicitudCotizacionItem ya resuelven bien
#     porque ServicioPublicado quedó cargado en el paso anterior).
docker compose exec lab python manage.py loaddata /tmp/web_dump.json

# 2c. Revincula por código de facturación / nombre normalizado contra el
#     catálogo REAL de esta base. Dry-run por defecto — revisa el reporte
#     antes de repetir con --apply.
docker compose exec lab python manage.py revincular_catalogo /tmp/web_dump_relink.json
docker compose exec lab python manage.py revincular_catalogo /tmp/web_dump_relink.json --apply

docker compose exec lab rm /tmp/web_dump.json /tmp/web_dump_relink.json
```

`revincular_catalogo` nunca adivina: los casos ambiguos (dos `Servicio` con
nombre parecido) o sin match quedan reportados para vincular a mano desde el
admin (`autocomplete_fields`), igual que ya advierte
`poblar_catalogo_ensayos.py` para los ensayos con variantes en el LIMS.

**3. Pendiente manual después de aplicar**: reasignar en el admin la
categoría real de cada `ServicioPublicado` (quedó en "Sin categorizar
(pendiente)") y resolver los casos que `revincular_catalogo` reportó como
ambiguos o sin match.

### Producción

```bash
docker compose build
docker compose up -d
docker compose exec lab python manage.py migrate
docker compose exec lab python manage.py collectstatic --noinput
```

Los servicios `worker` (Celery, `-A grupovicaf worker`) y `beat`
(`-A grupovicaf beat`) corren en dev y prod. Tareas de más de ~1s:
estampado de QR + notificación del `InformeFinal` y los correos del
formulario de contacto (`web_contacto.tasks`). Periódicas (`beat`):
barrido diario de proyectos con `fecha_entrega_estimada` vencida
(`proyectos.tasks.notificar_proyectos_vencidos`, 07:30 America/Lima).
Sin `nginx` todavía — se añade en una fase posterior.

El **cache** usa Redis en la DB 0; el **broker/backend de Celery** en la
DB 1 de la misma instancia, para que limpiar el cache no borre la cola
(`_redis_db()` en `settings/base.py`; override con `CELERY_BROKER_URL` /
`CELERY_RESULT_BACKEND`).

Los estáticos/media viven en volúmenes nombrados (`static_volume`,
`media_volume`) compartidos entre `lab` y `web`, listos para que nginx los
sirva directamente cuando se añada.

### Local sin Docker

```bash
SITE_ROLE=lab python manage.py runserver 8000
SITE_ROLE=web python manage.py runserver 8001
SITE_ROLE=lab celery -A grupovicaf worker -l info   # requiere Redis local
SITE_ROLE=lab celery -A grupovicaf beat -l info     # tareas periódicas
```

## Flujo de trabajo

- Una rama por fase: `feat/f1-settings-split`, `feat/f2-docker`, etc.
- Revisar toda migración generada antes de commitear.
- Antes de cada commit: `SITE_ROLE=web python manage.py check --deploy`.
- Referencia del proyecto web anterior: `_ref/vicafpro` (solo lectura, ignorado por Git).
  Fixtures en `_ref/fixtures/`, media en `_ref/media_vicafpro/`.
