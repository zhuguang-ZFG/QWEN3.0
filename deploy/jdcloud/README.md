# JDCloud Ops Assets

This directory contains tracked, non-secret assets for the secondary JDCloud
node used by LiMa ops experiments.

## Role

- JDCloud node: `117.72.118.95`
- Current role: secondary provider-probe / monitoring node.
- Non-role: it is not the primary LiMa Router and does not replace
  `chat.donglicao.com/v1` for IDE or terminal-agent traffic.

## Tracked Assets

| File | Purpose |
|---|---|
| `deploy_probe_platform.sh` | Installs the provider-probe package, browser service, and discovery timer under `/opt/lima-probe`. |
| `install_playwright.sh` | Installs Playwright/Chromium dependencies and the browser service. |
| `lima-probe-browser.service` | systemd unit for the browser helper on port `8092` loopback. |
| `lima-probe.service` | oneshot systemd unit for provider discovery. |
| `lima-probe.timer` | timer for scheduled provider discovery. |
| `configure_*.sh`, `install_*.sh`, `nginx_hermes.conf` | Optional JDCloud service setup templates. Review before use. |

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
python -m py_compile provider_probe\browser_service.py provider_probe\discovery\scheduler.py
```

If a real JDCloud deployment is performed, record service status and smoke
evidence in `docs/ops/JDCLOUD_RUNTIME_STATUS.md`, `progress.md`, and
`findings.md`.
