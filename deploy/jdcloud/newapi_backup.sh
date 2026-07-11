#!/bin/bash
# Daily backup for NewAPI — MySQL dump + optional offsite (Aliyun SCP) / OSS.
# Env files (optional): /opt/newapi/.env.backup
#   NEWAPI_OFFSITE_HOST=47.112.162.80
#   NEWAPI_OFFSITE_PATH=/var/backups/newapi-offsite
#   NEWAPI_OFFSITE_SSH_KEY=/root/.ssh/id_ed25519_newapi_offsite
#   NEWAPI_OSS_URI=oss://bucket/prefix   # needs ossutil64
set -euo pipefail

NEWAPI_DIR="${NEWAPI_DIR:-/opt/newapi}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/newapi}"
KEEP_DAYS="${KEEP_DAYS:-14}"
TS=$(date +%Y%m%d_%H%M%S)
DEST="${BACKUP_ROOT}/${TS}"
ENV_FILE="${NEWAPI_DIR}/.env"
ENV_BACKUP="${NEWAPI_DIR}/.env.backup"
DB_SQLITE="${NEWAPI_DIR}/data/one-api.db"

mkdir -p "$DEST"

# shellcheck disable=SC1090
[ -f "$ENV_BACKUP" ] && set -a && . "$ENV_BACKUP" && set +a

load_db_env() {
  [ -f "$ENV_FILE" ] || return 0
  while IFS= read -r line; do
    case "$line" in
      NEWAPI_MYSQL_USER=*|NEWAPI_MYSQL_PASS=*|SQL_DSN=*) export "$line" ;;
    esac
  done < <(grep -E '^(NEWAPI_MYSQL_USER|NEWAPI_MYSQL_PASS|SQL_DSN)=' "$ENV_FILE" || true)
}

load_db_env

if [ -n "${SQL_DSN:-}" ] && [ -n "${NEWAPI_MYSQL_USER:-}" ] && [ -n "${NEWAPI_MYSQL_PASS:-}" ]; then
  echo "[INFO] MySQL dump"
  mysqldump --no-tablespaces -u"$NEWAPI_MYSQL_USER" -p"$NEWAPI_MYSQL_PASS" -h127.0.0.1 \
    --single-transaction --routines --triggers newapi \
    | gzip -c > "$DEST/newapi.sql.gz"
  [ -f "$DB_SQLITE" ] && gzip -c "$DB_SQLITE" > "$DEST/one-api.db.gz.cold" || true
else
  echo "[INFO] SQLite backup"
  [ -f "$DB_SQLITE" ] || { echo "[ERROR] missing $DB_SQLITE"; exit 1; }
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB_SQLITE" ".backup '$DEST/one-api.db'"
  else
    cp -a "$DB_SQLITE" "$DEST/one-api.db"
  fi
  gzip -f "$DEST/one-api.db"
fi

cp -a "${NEWAPI_DIR}/docker-compose.yml" "$DEST/" 2>/dev/null || true
if [ "${NEWAPI_BACKUP_ENV:-0}" = "1" ] && [ -f "$ENV_FILE" ]; then
  cp -a "$ENV_FILE" "$DEST/.env"
  chmod 600 "$DEST/.env"
fi

echo "[INFO] wrote $DEST ($(du -sh "$DEST" | awk '{print $1}'))"
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+${KEEP_DAYS}" -exec rm -rf {} \;

# --- offsite: SCP to second VPS (default Aliyun) ---
if [ -n "${NEWAPI_OFFSITE_HOST:-}" ]; then
  KEY="${NEWAPI_OFFSITE_SSH_KEY:-/root/.ssh/id_ed25519_newapi_offsite}"
  RPATH="${NEWAPI_OFFSITE_PATH:-/var/backups/newapi-offsite}"
  echo "[INFO] offsite scp → ${NEWAPI_OFFSITE_HOST}:${RPATH}/${TS}"
  ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    "root@${NEWAPI_OFFSITE_HOST}" "mkdir -p '${RPATH}/${TS}'"
  scp -i "$KEY" -o BatchMode=yes -r "$DEST"/* "root@${NEWAPI_OFFSITE_HOST}:${RPATH}/${TS}/"
  ssh -i "$KEY" -o BatchMode=yes "root@${NEWAPI_OFFSITE_HOST}" \
    "find '${RPATH}' -mindepth 1 -maxdepth 1 -type d -mtime +${KEEP_DAYS} -exec rm -rf {} \;"
  echo "[INFO] offsite OK"
fi

# --- optional object storage ---
if [ -n "${NEWAPI_OSS_URI:-}" ]; then
  if command -v ossutil64 >/dev/null 2>&1; then
    ossutil64 cp -r "$DEST" "${NEWAPI_OSS_URI%/}/${TS}/"
  elif command -v aliyun >/dev/null 2>&1; then
    aliyun oss cp "$DEST" "${NEWAPI_OSS_URI%/}/${TS}/" --recursive
  else
    echo "[WARN] NEWAPI_OSS_URI set but no ossutil64/aliyun CLI" >&2
  fi
fi

echo "[OK] backup complete $TS"
