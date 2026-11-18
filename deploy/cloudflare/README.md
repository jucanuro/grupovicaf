# Correo real: Cloudflare recibe (Paso 4) y Amazon SES envía (Paso 5)

Ningún secreto va al repositorio: todo en el `.env` del servidor y en las
variables secretas del Worker.

## Paso 4 · Recibir con Cloudflare Email Routing

1. Genera el secreto: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   Ponlo en el `.env` como `CORREO_WEBHOOK_SECRET` y reinicia los servicios.
2. Cloudflare → Workers y Pages → Crear Worker `correo-entrante`; pega
   `correo-entrante.js`. En Ajustes → Variables: `URL_ENTRANTE`
   (`https://email.grupovicaf.com/api/entrante/`), `SECRETO` (tipo secreto, el mismo
   valor) y, opcional, `RESPALDO` (dirección verificada para no perder correos si
   el LIMS está caído).
3. Email Routing en un **subdominio piloto** (p. ej. `entrada.grupovicaf.com`):
   regla «Enviar a un Worker» → `correo-entrante`. Así el MX de la raíz sigue en
   cPanel hasta el corte final.
4. nginx del host `email.`: `client_max_body_size 40m;`.
5. En el `.env`: `CORREO_ENTRADA_ALIAS=entrada.grupovicaf.com=grupovicaf.com`, para que
   `informes@entrada.grupovicaf.com` llegue a la cuenta `informes@grupovicaf.com`.
   Prueba escribiéndole desde Gmail. En el corte final (MX de la raíz a Cloudflare)
   el alias deja de hacer falta.

Respuestas del webhook: 202 recibido · 404 la cuenta no existe (el Worker rechaza
con 550) · 401 firma/fecha inválida · 413 demasiado grande · 503 sin secreto.

## Paso 5 · Enviar por Amazon SES

1. SES → SMTP settings → crear credenciales SMTP. En el `.env`:
   `CORREO_ENVIO=smtp`, `CORREO_SMTP_HOST=email-smtp.us-east-1.amazonaws.com`,
   `CORREO_SMTP_PUERTO=587`, `CORREO_SMTP_USUARIO`, `CORREO_SMTP_CLAVE`.
2. Rebotes y quejas: SES → Configuration sets → `vicaf-correo` → destino de eventos
   (Bounce, Complaint) → tema SNS `vicaf-correo-eventos` → suscripción HTTPS a
   `https://email.grupovicaf.com/api/ses/<CORREO_SES_TOKEN>/`.
   En el `.env`: `CORREO_SES_CONFIG_SET=vicaf-correo`, `CORREO_SES_TOKEN` (aleatorio),
   `CORREO_SES_TOPIC_ARN` (ARN del tema).
   La suscripción se confirma sola.
3. Mientras SES siga en sandbox solo envía a direcciones verificadas.
