# Onboarding — GRUPO VICAF

Orientación para alguien nuevo en este repositorio. Antes de tocar código, conviene
entender el negocio: cada pantalla y cada app existen para un paso concreto del
proceso real del laboratorio, no son módulos genéricos de un CRM.

## 1. El negocio

**GRUPO VICAF** es un **laboratorio de ensayo de materiales y geotecnia**,
acreditado por INACAL (el organismo peruano de acreditación), con sede en
Cajamarca y cobertura en el norte del Perú. Hacen ensayos de suelos, concreto,
agregados, rocas y agua — por ejemplo "¿este concreto aguanta la carga que dice
el diseño?" o "¿este terreno es apto para cimentar?". Los clientes son
constructoras, municipalidades y mineras.

## 2. Qué es el software: dos sitios, un solo código

```
laboratorio.grupovicaf.com  → el LIMS (sistema interno del laboratorio)
www.grupovicaf.com          → la web pública (institucional, servicios, contacto)
```

Mismo repositorio y misma base de datos, pero **dos procesos separados**
(`SITE_ROLE=lab` / `SITE_ROLE=web`, cada uno con su propio `gunicorn`). Así, un
PDF pesado generándose en el LIMS nunca frena la web pública. El detalle
completo está en `CLAUDE.md`.

La mayor parte del trabajo de mantenimiento cae en el **LIMS** — es donde está
la complejidad real del negocio.

## 3. El flujo de trabajo real del laboratorio

Este es el proceso que hay que tener en la cabeza — cada app del LIMS existe
para un paso de esta cadena:

```
1. CLIENTE se registra                        (app: clientes)
        ↓
2. Se arma una COTIZACIÓN                      (app: servicios)
   - se eligen ensayos del catálogo (Servicio / Norma / Método)
   - se arma el precio y las condiciones de la oferta
     (ver docs/form-validador.md → Paso 4, basado en el formulario
     VCF-LAB-FOR-001 que usaba el laboratorio en Word)
        ↓
3. El cliente acepta → se crea un PROYECTO     (app: proyectos)
        ↓
4. El cliente entrega las muestras físicas →
   RECEPCIÓN DE MUESTRAS                       (app: proyectos)
   - se codifican, se pesan, se registran
        ↓
5. Se arma la SOLICITUD DE ENSAYO              (app: proyectos)
   - qué ensayo, con qué norma/método, para cuándo, quién lo hace
        ↓
6. El técnico EJECUTA el ensayo y
   registra resultados                         (app: actividades)
        ↓
7. Se emite el INFORME FINAL (PDF con QR
   de validación pública)                      (app: proyectos)
```

El menú lateral del LIMS (Cotizaciones, Proyectos, Muestras, Ensayos, Informes,
Calendario) refleja exactamente estos pasos, en el mismo orden. No son módulos
sueltos: cada modelo tiene una FK al paso anterior (`Proyecto.cotizacion`,
`RecepcionMuestra.cotizacion`, `SolicitudEnsayo.recepcion`, etc.).

## 4. Mapa de apps

| App | Para qué existe |
|---|---|
| `core` | login, dashboard con métricas del negocio |
| `clientes` | quién pide los ensayos — RUC, razón social, y un **código confidencial** (para que los informes no expongan el nombre real del cliente en la validación pública por QR) |
| `servicios` | el catálogo (`Norma`, `Método`, `Servicio` = qué ensayos existen y cuánto cuestan) + `Cotizacion` (paso 2 del flujo) |
| `proyectos` | `Proyecto`, `RecepcionMuestra`, `SolicitudEnsayo`, `InformeFinal` — pasos 3 a 7 |
| `actividades` | ejecución de ensayos y calendario del laboratorio |
| `trabajadores` | personal del laboratorio, con **rol y permisos por módulo** (`PermisoModulo` = módulo × acción, ej. `cotizaciones.crear`) |
| `web_*` (8 apps, prefijo obligatorio) | la web pública — **nunca duplica modelos del LIMS**, solo los lee con lista blanca de campos (RUC, montos y vouchers nunca pueden llegar a una vista pública — regla no negociable, ver `CLAUDE.md`) |

## 5. Cómo correrlo en local

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml exec lab python manage.py migrate
```

`lab` = LIMS en `:8000`, `web` = pública en `:8001`, `db` = Postgres 16, `redis`
= cache + cola de Celery. Toda tarea de más de ~1 segundo (PDF, QR, correo, SMS)
va a Celery en segundo plano, nunca bloquea al usuario.

Para tener datos de prueba sin arrancar de una base vacía:

```bash
docker compose -f docker-compose.dev.yml exec lab python cargar_clientes.py
docker compose -f docker-compose.dev.yml exec lab python cargar_servicios.py
docker compose -f docker-compose.dev.yml exec lab python manage.py sembrar_demo
```

Esto genera clientes, catálogo de ensayos, ~50 cotizaciones, ~40 proyectos,
recepciones y solicitudes — toda la cadena, con datos ficticios pero
coherentes, para navegar el sistema sin riesgo sobre datos reales. El dataset
demo queda marcado (`COT-DEMO-*`, `PROY-DEMO-*`, etc.) y es borrable con
`sembrar_demo --reset`.

## 6. Documentos para leer, en orden

1. **`CLAUDE.md`** (raíz del repo) — las reglas no negociables del proyecto:
   qué no se puede duplicar, qué campos nunca van a una vista pública,
   convenciones SEO de la web, comandos de Docker/deploy.
2. **`CHANGELOG.md`** — qué cambió y cuándo, en español, agrupado por fecha.
3. **`docs/form-validador.md`** — el módulo de validación en vivo de
   formularios, si hay que tocar cualquier formulario de captura del LIMS.

## 7. Detalles de estilo que sorprenden al llegar de otro proyecto Django

- **No se usa `django.forms`.** Todas las vistas de creación/edición parsean
  `request.POST` a mano (`request.POST.get('campo')`, validación manual,
  `Model.objects.create(...)`). Esto significa que `max_length` del modelo
  **no se valida solo** — hay que chequearlo a mano en la vista o vía
  `full_clean()` explícito, si no, un valor demasiado largo llega crudo a
  Postgres y revienta con `value too long for type character varying(N)`.
- **AWS (producción) es la fuente de verdad del LIMS.** Los datos reales de
  clientes/cotizaciones/proyectos nunca se sobreescriben desde dev — ver la
  sección "Actualizar contenido web sin tocar el LIMS" en `CLAUDE.md` para el
  procedimiento correcto cuando hay que subir solo contenido de la web
  pública.
- **Los permisos son por módulo y acción**, no los grupos/permisos nativos de
  Django — revisar `trabajadores.models.PermisoModulo` antes de asumir que
  `user.has_perm(...)` funciona como en otro proyecto.
