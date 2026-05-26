#!/usr/bin/env bash
# VPS cron: verify local LiMa router /health then ping Healthchecks.io (INF-B).
# Example crontab (every 5 min):
#   */5 * * * * LIMA_HEALTHCHECK_ENABLED=1 HEALTHCHECK_LIMA_VPS_URL=https://hc-ping.com/... /opt/lima-router/scripts/vps_router_healthcheck.sh >> /var/log/lima-healthcheck.log 2>&1
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec python3 scripts/healthcheck_ping.py \
  --env-key HEALTHCHECK_LIMA_VPS_URL \
  --check "${LIMA_HEALTH_URL:-http://127.0.0.1:8080/health}"
