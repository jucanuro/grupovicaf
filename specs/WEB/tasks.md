# VCF-WEB · Tasks · Asistente de WhatsApp

| Versión | Fecha | Estado |
|---|---|---|
| v2 | 2026-10-23 | Implementado (T1-T6 en v1, T7-T10 en v2) |

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

## Trazabilidad HU → REQ
| HU | REQ |
|---|---|
| HU-WEB-01 | 01, 03, 04, 05, 06 |
| HU-WEB-02 | 07, 08, 09, 10, 20, 21 |
| HU-WEB-03 | 11, 12, 13, 14, 15 |
| HU-WEB-04 | 02, 16, 18, 19 |
| HU-WEB-06 | 17, 18 |
| HU-WEB-07 | 04, 22, 23, 24, 25, 26, 27, 28, 29 |
| HU-WEB-05 | fuera de alcance (opción C) |
