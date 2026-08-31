# GRUPO VICAF — Contexto del proyecto

## Qué es esto

Proyecto Django único que sirve **dos sitios** desde el mismo código y la misma base de datos:

| Rol | Dominio | `SITE_ROLE` | URLconf |
|---|---|---|---|
| Web institucional pública | `www.grupovicaf.com` | `web` | `grupovicaf/urls_web.py` |
| LIMS (sistema de laboratorio) | `laboratorio.grupovicaf.com` | `lab` | `grupovicaf/urls_lab.py` |

Se ejecutan como **dos procesos gunicorn separados** con distinta variable de entorno
`SITE_ROLE`, para que un informe PDF pesado del laboratorio nunca frene la web pública.

El negocio: laboratorio de ensayo de materiales y geotecnia acreditado por INACAL, con
sede en Cajamarca y cobertura en el norte del Perú.

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

### Capa web (pública) — prefijo `web_` obligatorio

| App | Responsabilidad |
|---|---|
| `web_inicio` | Carrusel y home |
| `web_nosotros` | Misión, visión, documentos |
| `web_acreditacion` | Acreditación INACAL y alcance |
| `web_catalogo` | Publicación sobre `servicios`, `clientes` y `trabajadores` |
| `web_zonas` | Landing pages por ciudad de cobertura |
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
`web_acreditacion`, `web_catalogo`, `web_zonas`, `web_contacto`,
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
