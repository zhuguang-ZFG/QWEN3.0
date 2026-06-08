# LiMa Online Distributions

> Updated: 2026-06-09
> Scope: VPS-hosted public surfaces that belong to the LiMa project and must be controlled from this repository.

## Rule

The official website, open platform, chat interface, FRP endpoint, nginx edge, and supporting public services are LiMa distributions. Any change to these surfaces must update this repository before or in the same commit as the VPS change.

Required repository updates:

- `docs/ONLINE_DISTRIBUTIONS.md` for inventory and policy changes.
- `infra/vps/nginx/*.conf` for sanitized nginx config snapshots.
- `infra/vps/systemd/*.service` for sanitized systemd service snapshots.
- `scripts/smoke_online_distributions.py` when smoke expectations change.
- `STATUS.md`, `docs/LIMA_MEMORY.md`, and `progress.md` for operational evidence.

Do not commit secrets, cert private keys, provider tokens, database dumps, generated `.next/`, `node_modules/`, or local binary/software downloads.

## Inventory

| Surface | Public URL | VPS runtime | Source/control in repo | Purpose | Current policy |
|---|---|---|---|---|---|
| Official website | `https://www.donglicao.com`, `https://donglicao.com` | nginx root `/www/wwwroot/donglicao-site`; demo proxy `/api/demo` to LiMa router | `infra/vps/nginx/www.donglicao.com.conf`; local site source currently lives in nested `net/` working tree and must be imported without `.git`, build output, or large binaries before source changes are treated as tracked | Public product/brand entry and LiMa demo | Managed distribution; marketing/commercial direction remains paused unless user changes it. |
| Chat interface | `https://chat.donglicao.com` | nginx root `/var/www/chat`; `/v1`, `/health`, `/agent`, `/mcp`, `/device` proxy to `127.0.0.1:8080`; `/ws/voice` proxies to `127.0.0.1:8091`; retired `/telegram/*` paths must stay unavailable | `infra/vps/nginx/chat.donglicao.com.conf`; LiMa runtime in tracked Python modules | Private chat UI plus OpenAI/Anthropic-compatible API and device edge | Primary private coding-assistant endpoint. |
| Open platform / API compatibility | `https://api.donglicao.com` | nginx proxy to `/opt/ai-router/ai_router_mcp.py` on `127.0.0.1:8769`; retired `/telegram/*` paths return edge 404 | `infra/vps/nginx/api.donglicao.com.conf`; New API/One API runtimes are retained on VPS but are not the current nginx target for this host | Existing compatibility gateway state, not the primary LiMa IDE endpoint | Retained but not active commercial rollout. `chat.donglicao.com/v1` remains the primary private coding API. |
| FRP endpoint | `http://47.112.162.80:8088` | VPS `frps` maps to Windows LiMa API `127.0.0.1:8080` | `docs/LOCAL_PROXY_RUNTIME_STATUS.md`, `frp/frpc.toml` when tracked | Public validation path for Windows local-router and local proxy providers | Operational smoke path, not the preferred HTTPS IDE endpoint. |
| LiMa router | local service, public through nginx/FRP | `lima-router.service`, working dir `/opt/lima-router`, port `8080` | `infra/vps/systemd/lima-router.service`; runtime source in repo | Core FastAPI router | Secrets must live in `/opt/lima-router/.env`, not service unit files. |
| Voice gateway | public only through chat nginx websocket path | `lima-voice.service`, working dir `/opt/lima-voice`, port `8091` | `infra/vps/systemd/lima-voice.service`; `voice_gateway_deploy.sh`/voice files when used | Voice websocket gateway | Secrets must live in `/opt/lima-voice/.env`, not service unit files. |
| LiMa Device Gateway | `https://chat.donglicao.com/device/v1/*` | nginx proxies `/device/v1/health`, `/device/v1/tasks`, `/device/v1/events`, and WebSocket `/device/v1/ws` to `127.0.0.1:8080`; VPS production uses Redis task queues and Redis pub/sub task notifications across router processes | `routes/device_gateway.py`, `device_gateway/*`, `infra/vps/nginx/chat.donglicao.com.conf`, `docs/superpowers/plans/2026-05-24-lima-direct-device-gateway.md`, `docs/superpowers/plans/2026-05-25-lima-device-gateway-ha.md` | Direct U8/ESP32 device backend | Public behind per-device token auth. Redis HA mode is deployed for realtime multi-process task delivery; Postgres remains a later audit/history store. |

## Edge Policy

- Public HTTPS goes through nginx on ports `80` and `443`.
- FRP public validation uses port `8088`.
- Direct public access to internal service ports such as `8080`, `3003`, `8769`, `8091`, and `6379` must remain blocked by firewall/cloud security group even if services bind `0.0.0.0`.
- `api.donglicao.com` is a compatibility surface, not a license to revive public commercial platform work.
- `chat.donglicao.com/v1` is the primary IDE/agent base URL.
- Retired `/telegram/*` paths must return 404 at the nginx edge on both `chat.donglicao.com` and `api.donglicao.com`.
- `/device/v1/*` is public through `chat.donglicao.com` only and requires
  per-device token auth. VPS production uses Redis shared queues plus pub/sub
  task notifications so the process that owns a local WebSocket session can
  drain tasks created by another process.

## Secret Policy

- nginx snapshots may include certificate paths but never private key material.
- systemd unit files must not contain provider keys, bot tokens, API tokens, or passwords.
- Service secrets belong in root-readable environment files on VPS:
  - `/opt/lima-router/.env`
  - `/opt/lima-voice/.env`
- If a secret is found in a unit file or docs, migrate it to an env file, restart the service, and record the migration in `progress.md`.
- Provider-side rotation is required if a secret was exposed outside root-only files.

## Current VPS Evidence

- `lima-router.service` and `lima-voice.service` are active after secret migration.
- `systemctl cat` snapshots no longer contain provider key lines.
- Service-unit secret backups were moved to `/root/secure-service-backups` with mode `600`.
- Latest public health check: `https://chat.donglicao.com/health` returned `status=ok`.
- Latest Telegram retirement edge check: public `POST /telegram/webhook` returned HTTP `404` on both `https://api.donglicao.com` and `https://chat.donglicao.com` after nginx backups `/etc/nginx/conf.d/donglicao.conf.bak-20260609-040449` and `/etc/nginx/conf.d/chat.donglicao.com.conf.bak-20260609-040449`.
- Latest device gateway health check: `https://chat.donglicao.com/device/v1/health` returned `status=ok` with Redis task store and Redis session bus.
- Latest post-migration smoke used `scripts/smoke_online_distributions.py --api-key lima-local --chat-exact ha_redis_guarded_ok` and passed `12/12`, including public `6379` guard.
- Redis HA code path is controlled by `LIMA_DEVICE_TASK_STORE`, `LIMA_DEVICE_SESSION_BUS`, and `LIMA_DEVICE_REDIS_URL`; VPS production is currently enabled with Redis on loopback only.

## Change Checklist

1. Update tracked source/config/docs first.
2. Run `python -m py_compile scripts/smoke_online_distributions.py`.
3. Run `python scripts/smoke_online_distributions.py --chat-exact <short-token>` after deployment.
4. If nginx changed, run `nginx -t` on VPS before reload.
5. If systemd changed, run `systemctl daemon-reload`, restart affected services, and verify `systemctl is-active`.
6. Update `STATUS.md`, `docs/LIMA_MEMORY.md`, and `progress.md`.
7. Commit and push only curated files.
