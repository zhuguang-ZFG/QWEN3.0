#!/bin/bash
# Fast SQLite→MySQL for /opt/newapi (JDCloud). Uses Tsinghua pip mirror.
# Downtime target: < 2 min after tool is ready.
set -euo pipefail

NEWAPI_DIR=/opt/newapi
DB_FILE=$NEWAPI_DIR/data/one-api.db
ENV_FILE=$NEWAPI_DIR/.env
COMPOSE=$NEWAPI_DIR/docker-compose.yml
VENV=$NEWAPI_DIR/.venv-mig
STAMP=$(date +%Y%m%d_%H%M%S)
PIP_IDX=https://pypi.tuna.tsinghua.edu.cn/simple

info() { echo "[INFO] $*"; }
die()  { echo "[ERROR] $*"; exit 1; }

cd "$NEWAPI_DIR"
[ -f "$DB_FILE" ] || die "missing $DB_FILE"
[ -f "$ENV_FILE" ] || die "missing $ENV_FILE"

MYSQL_USER=$(grep -E '^NEWAPI_MYSQL_USER=' "$ENV_FILE" | cut -d= -f2-)
MYSQL_PASS=$(grep -E '^NEWAPI_MYSQL_PASS=' "$ENV_FILE" | cut -d= -f2-)
[ -n "$MYSQL_USER" ] && [ -n "$MYSQL_PASS" ] || die "NEWAPI_MYSQL_* missing — re-run password setup"

info "0) Ensure sqlite3mysql via venv + mirror (timeout 90s)"
if [ ! -x "$VENV/bin/sqlite3mysql" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -U pip -i "$PIP_IDX" --timeout 30
  timeout 90 "$VENV/bin/pip" install -q sqlite3-to-mysql -i "$PIP_IDX" --timeout 30 \
    || die "pip install sqlite3-to-mysql timed out/failed"
fi
[ -x "$VENV/bin/sqlite3mysql" ] || die "sqlite3mysql still missing"

info "1) Backup SQLite"
cp -a "$DB_FILE" "/var/backups/newapi/one-api.pre-mysql.${STAMP}.db"
cp -a "$COMPOSE" "${COMPOSE}.bak.pre-mysql.${STAMP}"

info "2) Stop new-api"
docker-compose stop new-api

info "3) Reset empty newapi schema"
mysql -e "DROP DATABASE IF EXISTS newapi;"
mysql -e "CREATE DATABASE newapi DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
# ensure grants still work
mysql -e "GRANT ALL PRIVILEGES ON newapi.* TO '${MYSQL_USER}'@'127.0.0.1'; FLUSH PRIVILEGES;" 2>/dev/null || true

info "4) Import (host-side)"
"$VENV/bin/sqlite3mysql" \
  -f "$DB_FILE" \
  -d newapi \
  -u "$MYSQL_USER" \
  -p "$MYSQL_PASS" \
  -h 127.0.0.1 -P 3306 \
  --ignore-duplicate-keys --use-fulltext --mysql-insert-method IGNORE

info "5) AUTO_INCREMENT fix"
python3 <<'PY'
import subprocess
tables = subprocess.check_output(["mysql","-N","-e","SHOW TABLES FROM newapi;"], text=True).split()
for t in tables:
    cols = subprocess.check_output(["mysql","-N","-e",f"SHOW COLUMNS FROM newapi.`{t}` LIKE 'id';"], text=True).strip()
    if not cols:
        continue
    mx = int(subprocess.check_output(["mysql","-N","-e",f"SELECT IFNULL(MAX(id),0) FROM newapi.`{t}`;"], text=True).strip())
    subprocess.check_call(["mysql","-e",f"ALTER TABLE newapi.`{t}` AUTO_INCREMENT={mx+1};"])
    print(f"  {t} -> {mx+1}")
PY

info "6) Count check"
U_S=$(sqlite3 "$DB_FILE" 'SELECT COUNT(*) FROM users;'); U_M=$(mysql -N -e 'SELECT COUNT(*) FROM newapi.users;')
C_S=$(sqlite3 "$DB_FILE" 'SELECT COUNT(*) FROM channels;'); C_M=$(mysql -N -e 'SELECT COUNT(*) FROM newapi.channels;')
T_S=$(sqlite3 "$DB_FILE" 'SELECT COUNT(*) FROM tokens;'); T_M=$(mysql -N -e 'SELECT COUNT(*) FROM newapi.tokens;')
echo "users $U_S->$U_M channels $C_S->$C_M tokens $T_S->$T_M"
[ "$U_S" = "$U_M" ] && [ "$C_S" = "$C_M" ] && [ "$T_S" = "$T_M" ] || die "count mismatch"

info "7) Enable SQL_DSN in .env + patch compose"
python3 <<'PY'
from pathlib import Path
import re

env = Path("/opt/newapi/.env")
lines = []
sql_dsn = None
for line in env.read_text().splitlines():
    if line.startswith("# SQL_DSN="):
        line = line[2:].split("  #", 1)[0].strip()
    if line.startswith("SQL_DSN="):
        sql_dsn = line.split("=", 1)[1]
    lines.append(line)
if not any(l.startswith("SQL_DSN=") for l in lines):
    raise SystemExit("SQL_DSN missing in .env")
# ensure host.docker.internal form
if sql_dsn and "host.docker.internal" not in sql_dsn:
    # rebuild from parts
    user = passwd = None
    for l in lines:
        if l.startswith("NEWAPI_MYSQL_USER="):
            user = l.split("=", 1)[1]
        if l.startswith("NEWAPI_MYSQL_PASS="):
            passwd = l.split("=", 1)[1]
    sql_dsn = f"{user}:{passwd}@tcp(host.docker.internal:3306)/newapi?charset=utf8mb4&parseTime=True&loc=Local"
    lines = [l for l in lines if not l.startswith("SQL_DSN=")]
    lines.append(f"SQL_DSN={sql_dsn}")
env.write_text("\n".join(lines) + "\n")
env.chmod(0o600)

compose = Path("/opt/newapi/docker-compose.yml")
text = compose.read_text(encoding="utf-8")
if "host.docker.internal" not in text:
    text = re.sub(
        r"(  new-api:\n(?:.*\n)*?    restart: always\n)",
        r"\1    extra_hosts:\n      - \"host.docker.internal:host-gateway\"\n",
        text,
        count=1,
    )
if re.search(r"^\s*-\s*SQL_DSN=", text, re.M):
    text = re.sub(r"^\s*-\s*SQL_DSN=.*$", "      - SQL_DSN=${SQL_DSN}", text, flags=re.M)
else:
    text = re.sub(
        r"(env_file:\n\s+-\s+\.env\n\s+environment:\n)",
        r"\1      - SQL_DSN=${SQL_DSN}\n",
        text,
        count=1,
    )
for key, line in [("SQL_MAX_OPEN_CONNS", "SQL_MAX_OPEN_CONNS=100"), ("SQL_MAX_IDLE_CONNS", "SQL_MAX_IDLE_CONNS=50")]:
    if re.search(rf"^\s*-\s*{key}=", text, re.M):
        text = re.sub(rf"^\s*-\s*{key}=.*$", f"      - {line}", text, flags=re.M)
    else:
        text = re.sub(r"(^\s*-\s*SQL_DSN=.*\n)", rf"\1      - {line}\n", text, count=1, flags=re.M)
compose.write_text(text, encoding="utf-8")
print("compose+env patched")
PY

info "8) Recreate new-api on MySQL"
docker rm -f newapi_new-api_1 2>/dev/null || true
docker-compose up -d --no-deps new-api
sleep 12
curl -sf -m 10 http://127.0.0.1:3000/api/status >/dev/null || die "status failed after MySQL switch"
# prove MySQL in use: touch option and see mysql change, or check logs for sqlite path absence
docker logs --tail 15 newapi_new-api_1 2>&1 | tail -15
info "MySQL migration OK ${STAMP}"
