# Healthchecks.io Setup (INF-B)

Updated: 2026-05-26

## Purpose

Dead-man monitoring: if a cron/Task Scheduler job **stops running**, Healthchecks.io alerts you. This complements Telegram alerts (which fire when code runs but fails).

**Default off on VPS** until `HEALTHCHECK_LIMA_VPS_URL` is set. Enable in one step:

```powershell
# 1. Add to D:\GIT\.env (pick one):
#    HEALTHCHECKS_API_KEY=...          # from https://healthchecks.io/accounts/profile/
#    HEALTHCHECKS_PING_KEY=...          # project ping key + slug auto-provision
#    HEALTHCHECK_LIMA_VPS_URL=https://hc-ping.com/<uuid>

python scripts/provision_healthchecks.py
```

This updates local `.env`, syncs GitHub Actions variable `HEALTHCHECK_LIMA_VPS_URL`, installs VPS cron (`/etc/cron.d/lima-router-healthcheck`), sets `LIMA_HEALTHCHECK_ENABLED=1`, and smoke-pings.

**External dead-man (no Healthchecks account required):** `.github/workflows/lima-vps-deadman.yml` curls `https://chat.donglicao.com/health` every 5 minutes from GitHub Actions. Optional: set repo variable `HEALTHCHECK_LIMA_VPS_URL` so the workflow also pings Healthchecks.io on success/fail.

**Default off (legacy):** set `LIMA_HEALTHCHECK_ENABLED=1` only after ping URLs are configured and smoke-tested.

## Quick Start

1. Create a free account at [healthchecks.io](https://healthchecks.io/) — **login:** [https://healthchecks.io/accounts/login/](https://healthchecks.io/accounts/login/) (there is **no** `/checks/` page; use `/` after login).
2. Create checks (suggested):

| Check name | Period | Grace |
|------------|--------|-------|
| `lima-vps-router` | 5 min | 10 min | **Live 2026-05-26** — VPS cron + Email ON |
| `lima-windows-router` | 5 min | 10 min |
| `lima-frpc-tunnel` | 5 min | 10 min |
| `lima-vps-probe-weekly` | 7 days | 1 day |

3. Copy each ping URL (e.g. `https://hc-ping.com/<uuid>`) into `.env` — **never commit real URLs to git**.

```bash
LIMA_HEALTHCHECK_ENABLED=1
HEALTHCHECK_LIMA_VPS_URL=https://hc-ping.com/your-vps-uuid
HEALTHCHECK_LIMA_WINDOWS_URL=https://hc-ping.com/your-windows-uuid
HEALTHCHECK_FRPC_URL=https://hc-ping.com/your-frpc-uuid
HEALTHCHECK_PROBE_WEEKLY_URL=https://hc-ping.com/your-probe-uuid
```

## VPS (router)

```bash
# Dry run
python scripts/healthcheck_ping.py --dry-run --env-key HEALTHCHECK_LIMA_VPS_URL

# Manual smoke (force ping without enabling globally)
python scripts/healthcheck_ping.py --force --check http://127.0.0.1:8080/health \
  --env-key HEALTHCHECK_LIMA_VPS_URL

# Cron (see scripts/vps_router_healthcheck.sh)
*/5 * * * * cd /opt/lima-router && LIMA_HEALTHCHECK_ENABLED=1 \
  ./scripts/vps_router_healthcheck.sh >> /var/log/lima-healthcheck.log 2>&1
```

## Windows (local router / frpc)

After `LiMa-HealthCheck` task runs, optional ping:

```powershell
# Router ping after local /health OK
powershell -File D:\GIT\scripts\healthcheck_ping.ps1 `
  -EnvKey HEALTHCHECK_LIMA_WINDOWS_URL `
  -Check http://127.0.0.1:8080/health

# FRPC process alive (no pre-check)
powershell -File D:\GIT\scripts\healthcheck_ping.ps1 `
  -EnvKey HEALTHCHECK_FRPC_URL
```

`infra/lima-health.bat` calls the Windows router ping when `LIMA_HEALTHCHECK_ENABLED=1`.

## Weekly probe dead-man

After `probe_cf_new_models.py` completes (ping only, no apply required):

```bash
python scripts/healthcheck_ping.py --force --env-key HEALTHCHECK_PROBE_WEEKLY_URL
```

## Rollback

1. Set `LIMA_HEALTHCHECK_ENABLED=0` in `.env`.
2. Remove VPS cron line for `vps_router_healthcheck.sh`.
3. Healthchecks checks can stay (they will go red — expected until re-enabled).

## Related

- Plan: `docs/superpowers/plans/2026-05-26-infra-tools-integration.md` (INF-B)
- Module: `healthcheck_ping.py`
- Telegram alerts: `telegram_notify` (event-driven, not dead-man)
