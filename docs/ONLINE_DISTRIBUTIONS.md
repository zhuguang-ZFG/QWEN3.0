# LiMa Online Distributions

> Updated: 2026-05-24
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
| Chat interface | `https://chat.donglicao.com` | nginx root `/var/www/chat`; `/v1`, `/health`, `/agent`, `/mcp`, `/telegram`, `/device` proxy to `127.0.0.1:8080`; `/ws/voice` proxies to `127.0.0.1:8091` | `infra/vps/nginx/chat.donglicao.com.conf`; LiMa runtime in tracked Python modules | Private chat UI plus OpenAI/Anthropic-compatible API and device edge | Primary private coding-assistant endpoint. |
| Open platform | `https://api.donglicao.com` | nginx proxy to New API on `127.0.0.1:3003`, with LiMa branding sub-filters | `infra/vps/nginx/api.donglicao.com.conf`; New API DB/runtime retained on VPS | Existing OpenAI-compatible token gateway and UI | Retained but not active commercial rollout. Requires real New API token; `lima-local` is not valid here. |
| FRP endpoint | `http://47.112.162.80:8088` | VPS `frps` maps to Windows LiMa API `127.0.0.1:8080` | `docs/LOCAL_PROXY_RUNTIME_STATUS.md`, `frp/frpc.toml` when tracked | Public validation path for Windows local-router and local proxy providers | Operational smoke path, not the preferred HTTPS IDE endpoint. |
| LiMa router | local service, public through nginx/FRP | `lima-router.service`, working dir `/opt/lima-router`, port `8080` | `infra/vps/systemd/lima-router.service`; runtime source in repo | Core FastAPI router | Secrets must live in `/opt/lima-router/.env`, not service unit files. |
| Voice gateway | public only through chat nginx websocket path | `lima-voice.service`, working dir `/opt/lima-voice`, port `8091` | `infra/vps/systemd/lima-voice.service`; `voice_gateway_deploy.sh`/voice files when used | Voice websocket gateway | Secrets must live in `/opt/lima-voice/.env`, not service unit files. |
| LiMa Device Gateway | `https://chat.donglicao.com/device/v1/*` | nginx proxies `/device/v1/health`, `/device/v1/tasks`, `/device/v1/events`, and WebSocket `/device/v1/ws` to `127.0.0.1:8080`; current task store is memory-only single-node mode | `routes/device_gateway.py`, `device_gateway/*`, `infra/vps/nginx/chat.donglicao.com.conf`, `docs/superpowers/plans/2026-05-24-lima-direct-device-gateway.md` | Direct U8/ESP32 device backend | Public behind per-device token auth. Keep HA/shared-store rollout gated until Redis/Postgres plus sticky WebSocket routing or a session-owner broker is deployed. |

## Edge Policy

- Public HTTPS goes through nginx on ports `80` and `443`.
- FRP public validation uses port `8088`.
- Direct public access to internal service ports such as `8080`, `3003`, and `8091` must remain blocked by firewall/cloud security group even if services bind `0.0.0.0`.
- `api.donglicao.com` branding filters are a compatibility layer over New API, not a license to revive public commercial platform work.
- `chat.donglicao.com/v1` is the primary IDE/agent base URL.
- `/device/v1/*` is public through `chat.donglicao.com` only, requires
  per-device token auth, and currently uses memory-only single-node mode.
  HA/shared-store rollout remains gated until Redis/Postgres plus sticky
  WebSocket routing or a session-owner broker is deployed.

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
- Latest device gateway health check: `https://chat.donglicao.com/device/v1/health` returned `status=ok` with memory-only task store.
- Latest post-migration smoke used `scripts/smoke_online_distributions.py --api-key lima-local --chat-exact device_gateway_https_ok` and passed `11/11`.

## Change Checklist

1. Update tracked source/config/docs first.
2. Run `python -m py_compile scripts/smoke_online_distributions.py`.
3. Run `python scripts/smoke_online_distributions.py --chat-exact <short-token>` after deployment.
4. If nginx changed, run `nginx -t` on VPS before reload.
5. If systemd changed, run `systemctl daemon-reload`, restart affected services, and verify `systemctl is-active`.
6. Update `STATUS.md`, `docs/LIMA_MEMORY.md`, and `progress.md`.
7. Commit and push only curated files.
