# VCF-WEB · Tasks · Asistente de WhatsApp

| Versión | Fecha | Estado |
|---|---|---|
| v1 | 2026-10-15 | Implementado |

- [x] **T1 · Horario con receso y WhatsApp en dígitos** — `NegocioConfig`: campos de receso (migración 0008), datos 13:00 y 15:00 (migración 0009), `whatsapp_digitos`, `horario_texto()` y `esta_abierto()`. Cubre REQ-WEB-03, 18 y 19. Se verifica con `siteconfig/tests.py`.
- [x] **T2 · Saludo y catálogo público** — `web_contacto/asistente.py`: `saludo_para()` y `catalogo_publico()` con lista blanca. Cubre REQ-WEB-05, 07 y 10. Se verifica con `web_contacto/test_asistente.py`.
- [x] **T3 · Endpoint JSON** — `GET /contacto/asistente/`, sin caché para el saludo y 404 sin WhatsApp. Cubre REQ-WEB-02, 05, 07, 10, 18 y 19. Se verifica con `web_contacto/test_asistente.py`.
- [x] **T4 · Botón en todas las páginas** — partial incluido en `web/base.html`, botón de la home quitado, contacto con `whatsapp_digitos` y horario con receso en la home. Cubre REQ-WEB-01, 02 y 03. Se verifica con `web_contacto/test_asistente.py` (una sola aparición en /, /servicios/ y /contacto/).
- [x] **T5 · Asistente guiado (JS)** — `static/web/js/asistente-whatsapp.js` con los textos aprobados, el menú de 3 opciones, servicios, cotización paso a paso, asesor, aviso fuera de horario y wa.me. Cubre REQ-WEB-04, 06, 08, 09, 11 a 17. Se verifica con `node --test 'tests/js/*.test.js'` y una prueba E2E manual (ver README de pruebas en el reporte del hilo).
- [x] **T6 · Docs** — `docs/proc/VCF-WEB_HU_CU_v1.md` v1.4 y specs.

## Trazabilidad HU → REQ
| HU | REQ |
|---|---|
| HU-WEB-01 | 01, 03, 04, 05, 06 |
| HU-WEB-02 | 07, 08, 09, 10 |
| HU-WEB-03 | 11, 12, 13, 14, 15 |
| HU-WEB-04 | 02, 16, 18, 19 |
| HU-WEB-06 | 17, 18 |
| HU-WEB-05 | fuera de alcance (opción C) |
