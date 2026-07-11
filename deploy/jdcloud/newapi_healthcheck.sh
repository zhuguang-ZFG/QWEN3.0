#!/bin/bash
# NewAPI lightweight healthcheck — NO chat/completions (does not burn quota).
# Checks: loopback status, docker, claude-cache-proxy unit, optional Redis.
# Optional Healthchecks.io: set NEWAPI_HC_PING_UUID in /opt/newapi/.env.backup
# Cron example: */5 * * * * /opt/newapi/healthcheck.sh >> /var/log/newapi-healthcheck.log 2>&1
set -u

NEWAPI_DIR="${NEWAPI_DIR:-/opt/newapi}"
ENV_BACKUP="${NEWAPI_DIR}/.env.backup"
ENV_HC="${NEWAPI_DIR}/.healthcheck.env"
LOG_TS="$(date -Is)"
FAIL=0
MSGS=()

# shellcheck disable=SC1090
[ -f "$ENV_BACKUP" ] && set -a && . "$ENV_BACKUP" && set +a
# shellcheck disable=SC1090
[ -f "$ENV_HC" ] && set -a && . "$ENV_HC" && set +a

ok() { MSGS+=("OK  $1"); }
fail() { MSGS+=("FAIL $1"); FAIL=1; }

# 1) new-api loopback status
if curl -sf -m 8 "http://127.0.0.1:3000/api/status" | grep -q '"success"[[:space:]]*:[[:space:]]*true'; then
  ok "new-api :3000/api/status"
else
  fail "new-api :3000/api/status"
fi

# 2) container running
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qE 'new-api|newapi'; then
  ok "docker new-api running"
else
  fail "docker new-api not running"
fi

# 3) Claude cache proxy (systemd only — no HTTP chat)
if systemctl is-active --quiet claude-cache-proxy.service 2>/dev/null; then
  ok "claude-cache-proxy.service active"
elif ss -tlnp 2>/dev/null | grep -q ':3001'; then
  ok "claude-cache-proxy :3001 listening"
else
  fail "claude-cache-proxy down"
fi

# 4) Redis (optional — password from container REDIS_CONN_STRING)
CID=$(docker ps -qf name=new-api 2>/dev/null | head -1)
if [ -n "$CID" ]; then
  RURL=$(docker exec "$CID" printenv REDIS_CONN_STRING 2>/dev/null || true)
  RPASS=$(RURL="$RURL" python3 -c "
import os, re, urllib.parse
u = os.environ.get('RURL', '')
m = re.match(r'redis://:([^@]+)@', u)
print(urllib.parse.unquote(m.group(1)) if m else '')
" 2>/dev/null || true)
  if [ -n "$RPASS" ]; then
    if redis-cli -a "$RPASS" --no-auth-warning PING 2>/dev/null | grep -q PONG; then
      ok "redis PING"
    else
      fail "redis PING"
    fi
  elif redis-cli PING 2>/dev/null | grep -q PONG; then
    ok "redis PING (noauth)"
  else
    fail "redis PING"
  fi
fi

# Summary log line
echo "${LOG_TS} fail=${FAIL} ${MSGS[*]}"

# Optional Healthchecks.io (status-only UUID; never chat)
UUID="${NEWAPI_HC_PING_UUID:-${HTTPS_UUID:-}}"
if [ -n "$UUID" ]; then
  if [ "$FAIL" -eq 0 ]; then
    curl -fsS -m 10 --retry 2 "https://hc-ping.com/${UUID}" >/dev/null 2>&1 || true
  else
    curl -fsS -m 10 --retry 2 "https://hc-ping.com/${UUID}/fail" >/dev/null 2>&1 || true
  fi
fi

exit "$FAIL"
