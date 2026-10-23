# VCF-WEB · Tasks · Asistente de WhatsApp y certificaciones

| Versión | Fecha | Estado |
|---|---|---|
| v6 | 2026-10-23 | Implementado (T1-T6 en v1, T7-T11 en v2, T12-T16 en v3, T17-T20 en v4, T21 en v5, T22 en v6) |

- [x] **T1 · Horario con receso y WhatsApp en dígitos** — `NegocioConfig`: campos de receso (migración 0008), datos 13:00 y 15:00 (migración 0009), `whatsapp_digitos`, `horario_texto()` y `esta_abierto()`. Cubre REQ-WEB-03, 18 y 19. Se verifica con `siteconfig/tests.py`.
- [x] **T2 · Saludo y catálogo público** — `web_contacto/asistente.py`: `saludo_para()` y `catalogo_publico()` con lista blanca. Cubre REQ-WEB-05, 07 y 10. Se verifica con `web_contacto/test_asistente.py`.
- [x] **T3 · Endpoint JSON** — `GET /contacto/asistente/`, sin caché para el saludo y 404 sin WhatsApp. Cubre REQ-WEB-02, 05, 07, 10, 18 y 19. Se verifica con `web_contacto/test_asistente.py`.
- [x] **T4 · Botón en todas las páginas** — partial incluido en `web/base.html`, botón de la home quitado, contacto con `whatsapp_digitos` y horario con receso en la home. Cubre REQ-WEB-01, 02 y 03. Se verifica con `web_contacto/test_asistente.py` (una sola aparición en /, /servicios/ y /contacto/).
- [x] **T5 · Asistente guiado (JS)** — `static/web/js/asistente-whatsapp.js` con los textos aprobados, el menú de 3 opciones, servicios, cotización paso a paso, asesor, aviso fuera de horario y wa.me. Cubre REQ-WEB-04, 06, 08, 09, 11 a 17. Se verifica con `node --test 'tests/js/*.test.js'` y una prueba E2E manual (ver README de pruebas en el reporte del hilo).
- [x] **T6 · Docs** — `docs/proc/VCF-WEB_HU_CU_v1.md` v1.4 y specs.

### v2 · Cambio de alcance [Decisión Gerente] (2026-10-23)
- [x] **T7 · Docs v2** — HU v1.5 (HU-WEB-07, CU-WEB-03, CA-02.3/02.7, RN-12 a 14, flujo 8.1) y specs v2. Sin código.
- [x] **T8 · Endpoint con slug y URL solo si hay página** — `web_contacto/asistente.py`: `slug` en líneas y ensayos, y `url: null` si el ensayo no tiene página propia (slug resuelto por una línea). Cubre REQ-WEB-20 y 21. Se verifica con `web_contacto/test_asistente.py`.
- [x] **T9 · Estado persistente y navegación** — `static/web/js/asistente-whatsapp.js`: pila serializable, `sessionStorage`, restauración sin robar el foco, poda de pasos despublicados, "Ver en la web" en líneas y ensayos, botón "Menú principal", "Sí, cotizar" con el servicio elegido y cierre que no se reabre. Cubre REQ-WEB-04, 08, 20, 22 a 27 y 29. Se verifica con `tests/js/asistente-whatsapp.test.js` y con el recorrido E2E (capturas).
- [x] **T10 · Panel en móvil** — `templates/web/partials/asistente_whatsapp.html` y JS: panel a lo ancho con 16 px de margen, área de mensajes a 40 % del alto, botón flotante oculto con el panel abierto y `padding-bottom` en `body`. Cubre REQ-WEB-25 y 28. Se verifica con `web_contacto/test_asistente.py` (marcado del partial) y con capturas a 390 px y 1280 px.
- [x] **T11 · Defecto: botón flotante fuera de pantalla con CSS anterior** — la posición base vuelve a las clases de v1 (`bottom-5 right-5`) y lo de v2 pasa a variantes `max-sm:`, incluido `pointer-events`. Cubre REQ-WEB-01 y 28. Se verifica con `test_boton_flotante_visible_en_escritorio_y_movil` (home, /servicios/, detalle de línea y contacto) y con el recorrido en navegador con el `output.css` actual y con uno anterior a v2, en escritorio y móvil, y con cada estado de `sessionStorage`.

### v3 · Certificado ISO 9001 [Decisión Gerente] (2026-10-23)
- [x] **T12 · Docs v3** — HU v1.6 (HU-WEB-08, CU-WEB-04, RN-15, P-12 a P-15) y specs v3. Sin código.
- [x] **T13 · Modelo, admin y datos del certificado** — `Certificacion` con `publicadas()`, validadores del PDF, `clean()` del sello, admin con estado "Publicada", migraciones `0002` (esquema) y `0003` (ER-0146/2026 sin archivo). Cubre REQ-WEB-31 y 36. Se verifica con `web_acreditacion/tests.py` (`CertificacionModelTests`).
- [x] **T14 · Tarjeta ISO 9001 y visor del PDF** — vista, `tarjeta_certificacion.html`, `modal_certificado_pdf.html` y `certificado-pdf.js`. Cubre REQ-WEB-30 a 35. Se verifica con `web_acreditacion/tests.py` (`AcreditacionPaginaTests`), `node --test tests/js/certificado-pdf.test.js` y capturas en 1280 px (modal) y 390 px (pestaña nueva).
- [x] **T15 · PDF embebible** — `servir_certificado_dev` en `urls_web.py` y `location /media/certificaciones/` en nginx con `SAMEORIGIN`. Cubre REQ-WEB-37. Se verifica con `web_acreditacion/tests.py` (`CabecerasPdfTests`) y con el modal mostrando el PDF en dev. **Al desplegar:** copiar `deploy/nginx/grupovicaf.conf` al servidor, `sudo nginx -t` y `sudo systemctl reload nginx`.
- [x] **T16 · JSON-LD** — templatetag `certificaciones_jsonld` y `hasCertification` en `web/base.html`. Cubre REQ-WEB-38 y 31. Se verifica con `web_acreditacion/tests.py` (`JsonLdTests`, JSON válido y ausente si vence).

### v4 · Modelo único de certificaciones [Decisión Gerente] (2026-10-23)
- [x] **T17 · Docs v4** — HU v1.7 (HU-WEB-08 y CU-WEB-04 reescritos, RN-15, §2.5, PM-11, P-16 a P-18) y specs v4. Sin código.
- [x] **T18 · Modelo único, migración y cards con modal en Acreditación** — `Certificacion` con título, descripción, tipo, institución, archivo (imagen o PDF), vigencia opcional; migraciones `0004` (campos nuevos), `0005` (ISO 9001 convertido e INACAL LE-230 con la imagen del certificado) y `0006` (quita los campos de v3); admin; grilla de cards (`card_certificacion.html`), modal único de imagen o PDF (`modal_certificacion.html`, `certificaciones.js`, reemplaza a `certificado-pdf.js` y al modal INACAL) y JSON-LD. Reutiliza de T14 el modal, la trampa de foco y el criterio de escritorio; de T15 el `SAMEORIGIN`; de T16 el templatetag. Cubre REQ-WEB-37, 39 a 48, 50 y 51. Se verifica con `web_acreditacion/tests.py` y `node --test tests/js/certificaciones.test.js`.
- [x] **T19 · Home resumida** — sección de certificaciones con hasta 4 cards y "Ver todas", sin la imagen grande del certificado; badges INACAL al modal único. Cubre REQ-WEB-49 y 50. Se verifica con `web_inicio/tests.py` y capturas.
- [x] **T20 · Textos solo Cajamarca** — H1, meta de `/acreditacion/` y texto de la home sin "norte del Perú"; `NegocioConfig.descripcion` (meta description de la home) con la migración `siteconfig/0008_descripcion_solo_cajamarca`, que solo cambia el texto de la semilla. **Al integrar con `VCF-WEB/asistente-whatsapp`** (que trae `siteconfig/0008_negocioconfig_receso` y `0009`): correr `makemigrations siteconfig --merge`. Cubre REQ-WEB-52. Se verifica con `web_acreditacion/tests.py` y `web_inicio/tests.py`.

### v5 · Todo en cards: ensayos acreditados [Decisión Gerente] (2026-10-23)
- [x] **T21 · Ensayos acreditados en cards por línea, buscador, filtro y modal** — HU v1.8 (HU-WEB-09, CU-WEB-05, RN-16, PM-12, P-19) y specs v5; `ensayos_acreditados_por_linea()` en `web_acreditacion/views.py` (lista blanca, agrupación de REQ-WEB-54, URL de ficha con RN-14); `partials/ensayos_acreditados.html`, `card_ensayo.html` y `modal_ensayo.html`; `static/web/js/ensayos-acreditados.js` (búsqueda sin tildes, filtro por línea, conteo `aria-live` y modal accesible). Sin migraciones. Cubre REQ-WEB-53 a 61. Se verifica con `web_acreditacion/tests.py` (`EnsayosAcreditadosTests`) y `node --test tests/js/ensayos-acreditados.test.js`.

### v6 · Rediseño de certificaciones y lista de ensayos [Decisión Gerente] (2026-10-23)
- [x] **T22 · Cards con logo, home compacta y ensayos en lista** — HU v1.9 (CA-08.2, 08.4, 08.8, 08.13 a 15; CA-09.1, 09.3, 09.5, 09.10; P-20) y specs v6; `Certificacion.logo` (migración 0007) y admin con vista previa; `logo_certificacion.html`, `card_certificacion.html` en 3 franjas (y `compacta`), grilla flex centrada, modal con "Abrir documento"; `ensayos_acreditados.html` en lista plegable por línea, alfabética y en columnas; `ensayos-acreditados.js` solo buscador; se borran `card_ensayo.html` y `modal_ensayo.html`. Cubre REQ-WEB-62 a 70. Se verifica con `web_acreditacion/tests.py`, `web_inicio/tests.py` y `node --test 'tests/js/*.test.js'`.

## Trazabilidad HU → REQ
| HU | REQ |
|---|---|
| HU-WEB-01 | 01, 03, 04, 05, 06 |
| HU-WEB-02 | 07, 08, 09, 10, 20, 21 |
| HU-WEB-03 | 11, 12, 13, 14, 15 |
| HU-WEB-04 | 02, 16, 18, 19 |
| HU-WEB-06 | 17, 18 |
| HU-WEB-07 | 04, 22, 23, 24, 25, 26, 27, 28, 29 |
| HU-WEB-08 | v3: 30 a 38 (reemplazados en v4 salvo 37) · v4: 37, 39 a 52 (43, 44, 46 y 49 reemplazados en v6) · v6: 62 a 65 |
| HU-WEB-09 | v5: 53 a 61 (reemplazados en v6) · v6: 66 a 70 |
| HU-WEB-05 | fuera de alcance (opción C) |
