#!/usr/bin/env bash
# Grupo VICAF — actualización de despliegue (después del primer setup).
# Correr como el usuario dueño de /var/www/projects/grupovicaf (o con sudo -u).
# No toca la base de datos más allá de `migrate`; no hace backup por sí solo
# (el backup diario corre aparte, ver vicafbackup.timer) — si vas a aplicar
# una migración riesgosa, corre deploy/scripts/backup.sh a mano antes.
set -euo pipefail

PROJECT_DIR="/var/www/projects/grupovicaf"
VENV="$PROJECT_DIR/venv/bin"
RAMA="${1:-main}"

cd "$PROJECT_DIR"

echo "==> git pull origin $RAMA"
git fetch origin
git checkout "$RAMA"
git pull origin "$RAMA"

echo "==> pip install -r requirements.txt"
"$VENV/pip" install --no-cache-dir -r requirements.txt

echo "==> npm ci && build:css"
npm ci
npm run build:css

echo "==> migrate (settings.prod)"
DJANGO_SETTINGS_MODULE=grupovicaf.settings.prod "$VENV/python" manage.py migrate --noinput

echo "==> collectstatic (settings.prod)"
DJANGO_SETTINGS_MODULE=grupovicaf.settings.prod "$VENV/python" manage.py collectstatic --noinput

echo "==> check --deploy (rol web, solo informativo — no aborta el deploy)"
SITE_ROLE=web DJANGO_SETTINGS_MODULE=grupovicaf.settings.prod "$VENV/python" manage.py check --deploy || true

echo "==> restart de servicios"
sudo systemctl restart vicaflab.service
sudo systemctl restart vicafweb.service
sudo systemctl restart vicafworker.service
sudo systemctl restart vicafbeat.service

echo "==> healthcheck"
sleep 2
FALLÓ=0
for par in "vicaflab:/run/gunicorn/vicaflab.sock" "vicafweb:/run/gunicorn/vicafweb.sock"; do
    nombre="${par%%:*}"
    sock="${par##*:}"
    if curl -s -o /dev/null -w "  %{http_code}" --unix-socket "$sock" http://localhost/ ; then
        echo "  <- $nombre ($sock) responde"
    else
        echo "  !! $nombre ($sock) no responde"
        FALLÓ=1
    fi
done

for servicio in vicaflab vicafweb vicafworker vicafbeat; do
    if ! systemctl is-active --quiet "$servicio"; then
        echo "  !! $servicio no está activo (systemctl status $servicio)"
        FALLÓ=1
    fi
done

if [ "$FALLÓ" -ne 0 ]; then
    echo "==> DEPLOY CON PROBLEMAS — revisa journalctl -u vicaflab -u vicafweb -u vicafworker -u vicafbeat"
    exit 1
fi

echo "==> deploy OK"
