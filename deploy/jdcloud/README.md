# JDCloud Ops Assets

This directory contains tracked, non-secret assets for the secondary JDCloud
node used by LiMa ops experiments.

## Role

- JDCloud node: `117.72.118.95`
- Current roles: new-api (OpenAI API gateway, api.donglicao.com) + provider-probe / monitoring node.
- Non-role: it is not the primary LiMa Router and does not replace
  `chat.donglicao.com/v1` for IDE or terminal-agent traffic.

## Tracked Assets

| File | Purpose |
|---|---|
| `deploy_probe_platform.sh` | Installs the provider-probe package, browser service, discovery timer, and result-push timer under `/opt/lima-probe`. |
| `install_playwright.sh` | Installs Playwright/Chromium dependencies and the browser service. |
| `lima-probe-browser.service` | systemd unit for the browser helper on port `8092` loopback. |
| `lima-probe.service` | oneshot systemd unit for provider discovery. |
| `lima-probe.timer` | timer for scheduled provider discovery. |
| `push_probe_results.py` | Standalone script that pushes probe results to the LiMa main VPS ingress endpoint. |
| `lima-probe-push.service` | oneshot systemd unit that runs `push_probe_results.py`. |
| `lima-probe-push.timer` | timer that triggers the push service every 5 minutes. |
| `configure_*.sh`, `install_*.sh`, `nginx_hermes.conf` | Optional JDCloud service setup templates. Review before use. |
| `install_newapi.sh` | New API 一键安装脚本（复用宿主机 MySQL 8.0 + Redis 7.0，host 网络模式）。 |
| `configure_newapi_firewall.sh` | New API 专用 ufw 防火墙（保护 3000/3306/6379）。 |
| `newapi.nginx.conf` | New API nginx 反代 + 自签证书配置（api.donglicao.com，无需 certbot）。 |

## new-api 部署概览

- 容器: `calciumion/new-api:latest`，host 网络模式，端口 3000
- 数据库: 宿主机 MySQL 8.0（`newapi` 库，用户 `newapi`）
- 缓存: 宿主机 Redis 7.0
- 公网入口: `https://api.donglicao.com`（Cloudflare → 阿里云反代 → 京东云）
- 详细 runbook: `docs/ops/JDCLOUD_NEWAPI_DEPLOY.md`

## Local-Only Files

One-off password helpers, generated reports, console copy/paste commands, and
local diagnostics are intentionally ignored by the root `.gitignore`.

Do not commit:

- password-based Paramiko deploy helpers;
- copied shell command transcripts;
- generated `docs/JDCLOUD_*.md` reports;
- Redis passwords, SSH passwords, Grafana admin passwords, API keys, or session
  cookies.

## Credential Boundary

Tracked scripts must use one of these mechanisms:

- SSH keys configured outside the repository;
- environment variables read at runtime;
- manual operator input over a secure channel.

Do not add literal passwords or tokens to tracked files.

## Verification

After changing JDCloud assets, verify at least:

```powershell
git status --short
git diff --check
python -m py_compile packages/provider-probe-offline/provider_probe/browser_service.py packages/provider-probe-offline/provider_probe/discovery/scheduler.py
```

If a real JDCloud deployment is performed, record service status and smoke
evidence in `docs/ops/JDCLOUD_RUNTIME_STATUS.md`, `progress.md`, and
`findings.md`.
