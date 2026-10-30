# Pruebas E2E (Playwright)

Recorren en un navegador real los flujos que cruzan la web pública y el LIMS.
Son la evidencia automática del gate **G4 (QA)**: el job `e2e` del CI las corre
en cada PR contra `dev` y `main`, y un PR con una prueba en rojo no se integra.

| Archivo | Flujo | Criterios |
|---|---|---|
| `cotizacion-web.spec.js` | Formulario de `/contacto/` → bandeja *Cotizaciones › Solicitudes web* del lab | — |
| `validacion-informe.spec.js` | Página del QR del informe (`/proyectos/v/<uuid>/`) sin RUC ni código confidencial, con `noindex` | CLAUDE.md reglas 3 y 15 |
| `tecnico.spec.js` | El técnico ve solo sus ensayos y el código confidencial en vez del cliente | L3 |
| `asistente-whatsapp.spec.js` | Asistente de WhatsApp: menú, cotización, validaciones, enlace `wa.me`, fuera de horario | REQ-WEB-01, 04, 10 a 16, 18 |

## Correr en local (sin Docker)

```bash
npm ci
npx playwright install chromium          # una sola vez
E2E_PYTHON=venv/bin/python npm run test:e2e
```

Playwright levanta `lab` en :8000 y `web` en :8001 con `grupovicaf.settings.test_local`
(caché en memoria, Celery en modo eager). El lab corre `migrate` y
`sembrar_e2e` antes de escuchar. Sin `DB_HOST` usa `db.sqlite3`.

Para ver el navegador: `npx playwright test --headed`; para depurar paso a paso:
`npx playwright test --debug`; reporte con trazas: `npx playwright show-report`.

## Correr contra docker-compose.dev.yml

Si :8000 y :8001 ya responden, Playwright los reutiliza y **no siembra**:

```bash
docker compose -f docker-compose.dev.yml exec lab python manage.py sembrar_e2e
npx playwright test
```

## Datos de prueba

`python manage.py sembrar_e2e` (`core/management/commands/sembrar_e2e.py`) es
idempotente y solo corre con `DEBUG=True`. Crea usuarios `e2e.*`, un cliente,
una solicitud `SOL-E2E-0001` con informe y un ensayo publicado
`e2e-proctor-modificado`. Las pruebas leen esos valores de `e2e/datos.js`: si
cambia uno, cambia en los dos lados. Contraseña: `E2E_PASSWORD` o la de
`datos.js` (solo existe en bases de desarrollo y CI).

## Cómo se agrega una prueba nueva

Cada criterio EARS aprobado (`specs/<MOD>/requirements.md`) que se pueda ver
en pantalla se vuelve un `test(...)` con su ID en el nombre, p. ej.
`'... (REQ-WEB-18)'`. La prueba va en el mismo PR que el código que la hace pasar.
