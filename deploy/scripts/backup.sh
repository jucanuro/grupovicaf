#!/usr/bin/env bash
# Backup diario de Postgres (pg_dump -F c) + mediafiles (tar.gz), retención
# 7 días. Pensado para correr como vicafbackup.service (systemd), que ya
# inyecta las variables de /var/www/projects/grupovicaf/.env vía
# EnvironmentFile. Ejecutable a mano para probar: ./deploy/scripts/backup.sh
set -euo pipefail

PROJECT_DIR="/var/www/projects/grupovicaf"
BACKUP_DIR="/var/backups/grupovicaf"
RETENTION_DIAS=7
FECHA="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

: "${DB_NAME:?falta DB_NAME en el entorno}"
: "${DB_USER:?falta DB_USER en el entorno}"
: "${DB_PASSWORD:?falta DB_PASSWORD en el entorno}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"

echo "[backup] $(date -Iseconds) — volcando Postgres ($DB_NAME)..."
PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
    -F c -f "$BACKUP_DIR/grupovicaf_${FECHA}.dump" \
    "$DB_NAME"

echo "[backup] $(date -Iseconds) — empaquetando mediafiles..."
tar -czf "$BACKUP_DIR/mediafiles_${FECHA}.tar.gz" \
    -C "$PROJECT_DIR" mediafiles

echo "[backup] $(date -Iseconds) — purgando backups de más de ${RETENTION_DIAS} días..."
find "$BACKUP_DIR" -maxdepth 1 -type f \
    \( -name 'grupovicaf_*.dump' -o -name 'mediafiles_*.tar.gz' \) \
    -mtime "+${RETENTION_DIAS}" -delete

echo "[backup] $(date -Iseconds) — listo: $BACKUP_DIR/grupovicaf_${FECHA}.dump, $BACKUP_DIR/mediafiles_${FECHA}.tar.gz"
