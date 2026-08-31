# Despliegue: web institucional + LIMS en la misma EC2

Instancia: t3.small, 2 GB RAM, IP elástica `35.153.197.74`.
LIMS ya corre en `/var/www/projects/grupovicaf` (venv + gunicorn + nginx),
Postgres nativo (`grupovicaf_db` / `grupovicaf`, `127.0.0.1:5432`). La base de
producción **no se toca**: nada de `pg_restore` ni `loaddata` sobre las tablas
del LIMS.

Convenciones de este instructivo:
- Todo lo que empieza con `sudo` se corre como el usuario con sudo normal.
- Todo lo que empieza con `sudo -u www-data` se corre como el usuario de la
  app — ajusta si el LIMS ya corre con otro usuario (ver paso 0.1).
- `$PROJECT_DIR` = `/var/www/projects/grupovicaf`.

**Dónde hay corte de servicio**: marcado con 🔴 en cada paso. Todo lo demás
es preparación que no afecta al LIMS en producción.

---

## 0. Antes de empezar — diagnóstico y respaldo (no destructivo)

### 0.1 Identifica cómo corre el LIMS hoy

No asumas que ya es un `systemd` con el nombre que usamos abajo — confírmalo:

```bash
systemctl list-units --type=service | grep -iE 'vicaf|gunicorn|grupovicaf'
ps aux | grep gunicorn
cat /etc/nginx/sites-enabled/*   # busca el upstream/socket que usa hoy
sudo certbot certificates        # qué dominios ya tienen cert y cuándo vencen
whoami; ls -la /var/www/projects/grupovicaf | head -5   # usuario dueño
```

Anota: nombre del servicio actual, el socket/puerto que usa, el usuario que
lo corre y el archivo de nginx que lo sirve. Si el usuario no es `www-data`,
reemplázalo en los 5 archivos de `deploy/systemd/*.service` antes de
instalarlos.

### 0.2 Respaldo de emergencia (antes de tocar nada)

```bash
mkdir -p /var/backups/grupovicaf
PGPASSWORD='<DB_PASSWORD del .env actual>' pg_dump -h 127.0.0.1 -U grupovicaf \
    -F c -f /var/backups/grupovicaf/pre_deploy_$(date +%Y%m%d_%H%M%S).dump grupovicaf_db
tar -czf /var/backups/grupovicaf/pre_deploy_mediafiles_$(date +%Y%m%d_%H%M%S).tar.gz \
    -C /var/www/projects/grupovicaf mediafiles
cp /var/www/projects/grupovicaf/.env /var/backups/grupovicaf/.env.pre_deploy_$(date +%Y%m%d_%H%M%S)
sudo cp -r /etc/nginx/sites-available /var/backups/grupovicaf/nginx_sites_available_$(date +%Y%m%d_%H%M%S)
```

Este dump es tu red de seguridad — con esto puedes volver exactamente al
estado de antes si algo sale mal (ver **Plan de reversión** al final).

### 0.3 Verifica margen de RAM y crea swap si no hay

2 GB es justo para: Postgres nativo + 2 gunicorn (lab, 2 workers) + 2 gunicorn
(web, 2 workers) + celery worker (concurrency 2) + celery beat + Redis +
nginx. Si algo se llena de golpe (varios informes PDF a la vez), sin swap el
OOM killer puede matar Postgres o gunicorn.

```bash
free -h
swapon --show
```

Si `swapon --show` no muestra nada:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 1. Redis

```bash
sudo apt update
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
redis-cli ping   # debe responder PONG
```

Config por defecto (`127.0.0.1:6379`, sin password) es suficiente: solo lo
usan los servicios locales (cache DB 0, Celery broker/backend DB 1), no está
expuesto a internet.

---

## 2. Código y entorno

### 2.1 Traer el código con las apps `web_*` y los cambios de este paquete

```bash
cd /var/www/projects/grupovicaf
sudo -u www-data git status   # confirma que no hay cambios locales sin commitear
sudo -u www-data git pull origin main
```

Esto trae, entre otros, los archivos de `deploy/`, `.env.produccion.example`
y los cambios en `grupovicaf/settings/base.py`,
`grupovicaf/context_processors.py`, `templates/web/base.html` y
`grupovicaf/urls_web.py` que implementan `SITE_NOINDEX`.

### 2.2 Dependencias de Python y Node

```bash
sudo -u www-data venv/bin/pip install --no-cache-dir -r requirements.txt

# Si node/npm no están instalados en la instancia:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

sudo -u www-data npm ci
```

### 2.3 Completar el `.env`

**No reemplaces el `.env` existente** (tiene `SECRET_KEY`, `DB_*`, `EMAIL_*`
ya en uso). Añádele las claves nuevas de `.env.produccion.example`:

```bash
cat .env.produccion.example
sudo -u www-data nano /var/www/projects/grupovicaf/.env
# pega las líneas de .env.produccion.example al final, completa valores
```

Verifica en particular:
- `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST` ya existentes siguen apuntando
  a `grupovicaf_db` — no los toques.
- `SITE_NOINDEX=True` (por defecto, aunque no la pongas explícitamente el
  código ya asume `True` si falta la variable).

---

## 3. Migraciones + contenido web (no toca datos del LIMS)

Exporta `DJANGO_SETTINGS_MODULE` una vez por sesión de shell para no
repetirlo en cada comando:

```bash
export DJANGO_SETTINGS_MODULE=grupovicaf.settings.prod
cd /var/www/projects/grupovicaf
```

### 3.1 Migrar (aplica las migraciones de las apps `web_*`/`siteconfig`; las del LIMS ya deberían estar al día)

```bash
sudo -u www-data -E venv/bin/python manage.py migrate
```

### 3.2 Generar el paquete de contenido web — EN DEV (tu máquina), no en el servidor

```bash
docker compose -f docker-compose.dev.yml exec lab python manage.py exportar_datos_web --output-dir /tmp
docker compose -f docker-compose.dev.yml cp lab:/tmp/web_dump.json .
docker compose -f docker-compose.dev.yml cp lab:/tmp/web_dump_relink.json .
```

### 3.3 Copiar al servidor (scp, no por git — son datos, no código)

```bash
scp web_dump.json web_dump_relink.json <tu_usuario>@35.153.197.74:/tmp/
rm web_dump.json web_dump_relink.json   # no los dejes sueltos en tu máquina
```

### 3.4 Cargar y revincular contra el catálogo REAL de producción

```bash
# En el servidor, con DJANGO_SETTINGS_MODULE ya exportado (ver arriba):
sudo -u www-data -E venv/bin/python manage.py cargar_servicios_publicados /tmp/web_dump_relink.json
sudo -u www-data -E venv/bin/python manage.py loaddata /tmp/web_dump.json

# Dry-run primero — revisa el reporte de ambigüedades/sin-match antes de aplicar
sudo -u www-data -E venv/bin/python manage.py revincular_catalogo /tmp/web_dump_relink.json
sudo -u www-data -E venv/bin/python manage.py revincular_catalogo /tmp/web_dump_relink.json --apply

rm /tmp/web_dump.json /tmp/web_dump_relink.json
```

**Pendiente manual después**: reasignar en el admin (`/admin/`, rol lab) la
categoría real de cada `ServicioPublicado` (queda en "Sin categorizar
(pendiente)") y resolver los casos que `revincular_catalogo` reportó como
ambiguos o sin match. No bloquea el resto del despliegue.

---

## 4. Tailwind + estáticos

```bash
sudo -u www-data npm run build:css
sudo -u www-data -E venv/bin/python manage.py collectstatic --noinput
```

### 4.1 Chequeo previo a activar servicios

```bash
sudo -u www-data SITE_ROLE=web -E venv/bin/python manage.py check --deploy
```

Revisa los warnings — con `SECURE_SSL_REDIRECT`/`SESSION_COOKIE_SECURE`/
`CSRF_COOKIE_SECURE` en `True` (ver `.env.produccion.example`) debería salir
limpio o casi limpio.

---

## 5. Servicios systemd

```bash
sudo cp deploy/systemd/vicaflab.service deploy/systemd/vicafweb.service \
        deploy/systemd/vicafworker.service deploy/systemd/vicafbeat.service \
        deploy/systemd/vicafbackup.service deploy/systemd/vicafbackup.timer \
        /etc/systemd/system/
sudo systemctl daemon-reload
```

Si el usuario real del LIMS no es `www-data` (ver 0.1), edítalo en los 6
archivos ya copiados a `/etc/systemd/system/` antes de continuar.

Habilita todo (no arranca `vicaflab`/`vicafweb` en conflicto con el gunicorn
viejo todavía — eso es el cutover del paso 8):

```bash
sudo systemctl enable vicaflab.service vicafweb.service vicafworker.service vicafbeat.service vicafbackup.timer
sudo systemctl start vicafworker.service vicafbeat.service vicafbackup.timer
```

`vicafworker`/`vicafbeat` no pisan nada del servicio viejo (no escuchan
puerto/socket), así que arrancarlos ahora es seguro.

---

## 6. nginx

### 🔴 6.1 Fusiona la config (aquí puede haber una interrupción breve del LIMS)

`deploy/nginx/grupovicaf.conf` ya trae el bloque de `laboratorio.grupovicaf.com`
apuntando al nuevo socket `/run/gunicorn/vicaflab.sock`. **No lo copies a
ciegas** sobre la config existente — diferénciala primero:

```bash
diff /etc/nginx/sites-available/<archivo-actual-del-lims> deploy/nginx/grupovicaf.conf
```

Si la config actual tiene algo específico (headers, redirects, un
`client_max_body_size` distinto, WebSockets, etc.) que no está en el archivo
nuevo, agrégalo al bloque `laboratorio.grupovicaf.com` de
`deploy/nginx/grupovicaf.conf` antes de instalarlo.

```bash
sudo cp deploy/nginx/grupovicaf.conf /etc/nginx/sites-available/grupovicaf.conf
sudo ln -sf /etc/nginx/sites-available/grupovicaf.conf /etc/nginx/sites-enabled/grupovicaf.conf
# desactiva el site viejo del LIMS para que no compita por el mismo server_name
sudo rm -f /etc/nginx/sites-enabled/<archivo-actual-del-lims>
sudo mkdir -p /var/www/certbot
sudo nginx -t
```

Si `nginx -t` falla porque a esta altura todavía no hay certificado para
`grupovicaf.com`/`www.grupovicaf.com` (los bloques 443 los completa certbot
en el paso 7), comenta temporalmente esos dos bloques `server { listen 443
... }` de `grupovicaf.conf` (déjalos solo con el bloque 80 activo) y
descoméntalos después de correr certbot.

### 6.2 No recargues nginx todavía

Falta el cutover (paso 8) y los certificados (paso 7) — si recargas ahora con
`laboratorio.grupovicaf.com` sin cert nuevo emitido pero el `server{}` 443 ya
apuntando al socket viejo/nuevo mezclado, puedes tumbar el LIMS. Sigue el
orden de los pasos.

---

## 7. Certbot — certificados para los 3 dominios

```bash
sudo apt install -y certbot python3-certbot-nginx   # si no estaba instalado

# laboratorio.grupovicaf.com: si YA tenía cert válido (ver 0.1), no hace
# falta reemitir — certbot detecta el cert existente y lo deja.
sudo certbot --nginx -d laboratorio.grupovicaf.com

# grupovicaf.com + www.grupovicaf.com en un solo cert (DNS de ambos ya
# debe apuntar a 35.153.197.74 antes de este paso, o certbot falla el
# challenge HTTP-01):
sudo certbot --nginx -d grupovicaf.com -d www.grupovicaf.com

sudo certbot certificates   # confirma los 3 dominios cubiertos y vencimiento
sudo nginx -t
```

Certbot reescribe automáticamente los bloques `server { listen 443 }` de
`grupovicaf.conf` con las rutas de `ssl_certificate`/`ssl_certificate_key`
correctas — no hace falta editarlas a mano.

---

## 8. 🔴 Cutover — apagar el gunicorn viejo, prender los nuevos

**Downtime esperado**: segundos, no minutos — es un `stop`/`start` de
systemd + un `reload` de nginx (graceful, sin cortar conexiones ya
establecidas). Hazlo en horario de bajo tráfico igual, por si algo no cuadra.

```bash
# Para el gunicorn/servicio viejo del LIMS (nombre real del paso 0.1)
sudo systemctl stop <nombre-servicio-viejo>

sudo systemctl start vicaflab.service
sudo systemctl start vicafweb.service
sudo systemctl status vicaflab.service vicafweb.service --no-pager

# Sockets deben existir antes de recargar nginx
ls -la /run/gunicorn/

sudo systemctl reload nginx
```

Si el `server{}` viejo quedó deshabilitado del `sites-enabled` en el paso
6.1, este es el momento en que `laboratorio.grupovicaf.com` empieza a servir
desde `vicaflab.service` en vez del proceso anterior.

Desactiva (no borres todavía) el servicio viejo para que no reinicie solo:

```bash
sudo systemctl disable <nombre-servicio-viejo>
```

---

## 9. Verificación final

```bash
# Sockets responden
curl -s -o /dev/null -w "%{http_code}\n" --unix-socket /run/gunicorn/vicaflab.sock http://localhost/
curl -s -o /dev/null -w "%{http_code}\n" --unix-socket /run/gunicorn/vicafweb.sock http://localhost/

# HTTPS de punta a punta, los 3 dominios
curl -sI https://laboratorio.grupovicaf.com/ | head -1
curl -sI https://www.grupovicaf.com/ | head -1
curl -sI https://grupovicaf.com/ | head -1   # debe dar 301 -> www

# noindex activo (mientras SITE_NOINDEX=True)
curl -s https://www.grupovicaf.com/robots.txt   # debe ser "Disallow: /"
curl -s https://www.grupovicaf.com/ | grep -i 'name="robots"'   # noindex,nofollow

# Servicios arriba
systemctl status vicaflab vicafweb vicafworker vicafbeat --no-pager

# Celery responde (encola una tarea de prueba desde el shell si hace falta)
journalctl -u vicafworker -n 30 --no-pager
journalctl -u vicafbeat -n 20 --no-pager

# Login del LIMS sigue funcionando con datos reales (verificación manual en el navegador)
```

Cuando el contenido de `web_*` esté redactado y quieras que Google indexe:
cambia `SITE_NOINDEX=False` en `.env` y `sudo systemctl restart vicafweb`
(no hace falta tocar `vicaflab`, el LIMS nunca se indexa).

---

## 10. Backups automáticos

Ya quedaron habilitados en el paso 5 (`vicafbackup.timer`, corre
`deploy/scripts/backup.sh` todos los días 03:00 America/Lima, retención 7
días en `/var/backups/grupovicaf/`). Verifica:

```bash
systemctl list-timers vicafbackup.timer
sudo systemctl start vicafbackup.service   # corrida manual de prueba
ls -la /var/backups/grupovicaf/
```

---

## Actualizaciones siguientes

Usar `deploy/deploy.sh` (pull + migrate + build CSS + collectstatic +
restart + healthcheck). Sin backup automático incluido — si la migración es
riesgosa, corre `deploy/scripts/backup.sh` antes a mano.

```bash
cd /var/www/projects/grupovicaf
sudo -u www-data ./deploy/deploy.sh main
```

---

## Plan de reversión

Si algo falla **a mitad del cutover (paso 8)** o después:

1. **Reactivar el servicio viejo, apagar el nuevo**:
   ```bash
   sudo systemctl stop vicaflab.service vicafweb.service
   sudo systemctl start <nombre-servicio-viejo>
   ```
2. **Restaurar nginx**:
   ```bash
   sudo cp /var/backups/grupovicaf/nginx_sites_available_<fecha>/* /etc/nginx/sites-available/
   sudo ln -sf /etc/nginx/sites-available/<archivo-original> /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/grupovicaf.conf
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. **Si además ya corriste el paso 3.4 (loaddata/revincular) y algo quedó
   mal vinculado**: eso solo tocó tablas `web_*`/`siteconfig`, nunca las del
   LIMS (regla no negociable #1) — restaura solo esas apps desde el dump de
   `pre_deploy_*.dump` del paso 0.2 si hace falta, no todo el dump completo
   (evita pisar cambios del LIMS hechos en producción entre medio):
   ```bash
   pg_restore -h 127.0.0.1 -U grupovicaf -d grupovicaf_db --clean --if-exists \
       -t web_catalogo_serviciopublicado -t web_catalogo_lineaservicio \
       -t web_zonas_zonacobertura -t web_acreditacion_acreditacion \
       /var/backups/grupovicaf/pre_deploy_<fecha>.dump
   # (ajusta la lista de tablas según lo que de verdad se haya tocado)
   ```
4. **Certificados de certbot**: no revertir nada aquí — un cert de más no
   rompe el rollback; certbot no toca `laboratorio.grupovicaf.com` si ya
   tenía uno válido (ver paso 7).
5. Confirma el rollback con el mismo checklist del paso 9 contra el estado
   anterior.

El punto de no-retorno real es el paso 3.4 (`loaddata`/`revincular_catalogo
--apply`) porque escribe en la base de producción — por eso el dump de 0.2
es obligatorio *antes* de llegar ahí, no solo antes del cutover de nginx.
