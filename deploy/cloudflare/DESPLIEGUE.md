# Orden de despliegue del correo y corte final de cPanel

Cada fase se confirma antes de pasar a la siguiente. Si algo falla, el correo de
cPanel sigue funcionando hasta la Fase 6.

## Fase 1 · Fusionar y desplegar el código (sin cambiar nada visible)
1. Fusionar los PR #11 → #12 → #13 (en ese orden) a `dev`; luego `dev` → `main`.
2. En el servidor (`/var/www/projects/grupovicaf`, con el venv):
   `git pull`, `pip install -r requirements.txt`,
   `SITE_ROLE=lab DJANGO_SETTINGS_MODULE=grupovicaf.settings.prod python manage.py migrate`,
   `collectstatic --noinput` (con `SITE_ROLE=web` y `lab`, como ya se hace),
   reiniciar `vicaflab`, `vicafweb`, `vicafworker`, `vicafbeat`.
3. El worker debe escuchar la cola `correo` (`-Q celery,correo`). Verificar.
4. nginx: server para `email.grupovicaf.com` hacia el gunicorn `lab`, con
   `client_max_body_size 40m;` y certificado (`certbot --nginx -d email.grupovicaf.com`).
   En Cloudflare el registro `email` debe existir (nube gris).

## Fase 2 · Variables del `.env` del servidor (nunca por chat)
`CORREO_HOST=email.grupovicaf.com`, `CORREO_BASE_URL`, `LAB_BASE_URL`,
`CORREO_ALMACEN=r2` + `CORREO_R2_*`, `CORREO_ENVIO=smtp` + `CORREO_SMTP_*` (SES),
`CORREO_WEBHOOK_SECRET`, `CORREO_ENTRADA_ALIAS=entrada.grupovicaf.com=grupovicaf.com`,
`CORREO_SES_CONFIG_SET`, `CORREO_SES_TOKEN`, `CORREO_SES_TOPIC_ARN`.
Reiniciar servicios. Comprobar: `https://email.grupovicaf.com/entrar/` responde.

## Fase 3 · Cuentas
Con el permiso «Administrar Correo», crear en `/administrar/` las cuentas reales
(informes, laboratorio, gerencia…) y asignar accesos y roles por persona.

## Fase 4 · Piloto en el subdominio
Seguir `README.md` (Worker + Email Routing en `entrada.grupovicaf.com`).
Pruebas: Gmail → `informes@entrada…` (llega y se ve limpio); responder desde el LIMS
(sale por SES, llega a Gmail con SPF/DKIM/DMARC pass); adjunto grande; rebote a una
dirección inexistente (queda «Falló el envío»). Con SES en producción, enviar a un
cliente real de prueba.

## Fase 5 · Migrar el correo viejo
1. En cPanel, exportar cada buzón (copia completa por Respaldo, o IMAP con
   Thunderbird guardando como .eml).
2. Subir los .eml al servidor y, por buzón:
   `python manage.py recibir_eml carpeta/*.eml` (idempotente: repetir no duplica).
3. Revisar por muestreo que fechas, adjuntos e hilos estén bien y guardar una copia
   de los respaldos de cPanel fuera del hosting.
Confirmar antes si el hosting aloja algo más que correo.

## Fase 6 · Corte final (ventana corta, mejor fuera de horario)
1. Bajar el TTL del MX a 5 min un día antes.
2. En Cloudflare: Email Routing en el dominio raíz (agrega sus propios MX) y eliminar
   el MX `mail.grupovicaf.com`; regla «Enviar a un Worker» → `correo-entrante`.
3. SPF raíz: dejar `v=spf1 include:amazonses.com ~all` (quita cPanel y mailchannels).
   DMARC: subir de `p=none` a `quarantine` tras una semana sin fallos.
4. Probar recibir y enviar con cuentas reales; retirar `CORREO_ENTRADA_ALIAS`.
5. Tras 2 semanas sin incidencias, cancelar el hosting cPanel.

Reversa del corte: restaurar el MX anterior en Cloudflare (los registros viejos quedan
anotados en la guía DNS).
