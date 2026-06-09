# JDCloud Runtime Status

> Updated: 2026-06-09
> Scope: secondary JDCloud node used by LiMa ops/probe work.

## Summary

JDCloud is now treated as a real LiMa ops node, not as disposable scratch.
The current node is `117.72.118.95` and is used for secondary
provider-probe / monitoring experiments.

Primary LiMa production traffic remains on:

```text
https://chat.donglicao.com/v1
```

The JDCloud node must not become a second public API surface without a separate
design, security review, and smoke plan.

## Current Role

| Item | Status |
|---|---|
| Public IP | `117.72.118.95` |
| Role | Secondary provider-probe / monitoring node |
| Primary API replacement | No |
| Credential storage | Outside Git only |
| Tracked deploy assets | `deploy/jdcloud/` shell and systemd templates |
| Local scratch policy | Ignored by exact `.gitignore` rules |
| Latest read-only smoke | `ok=true`, `chat_health_http_code=200`, `lima_probe_timer=active` |

## First Production Use

JDCloud should improve LiMa by taking low-risk monitoring and probe work off the
primary VPS, while keeping all user-facing IDE/agent traffic on
`chat.donglicao.com`.

Initial responsibilities:

1. Check primary LiMa health and Prometheus scrape reachability.
2. Run provider discovery/probe timers from a second network location.
3. Report sanitized capacity and service state for the JDCloud node.

Non-goals:

1. Do not expose a second public LiMa Router API from JDCloud.
2. Do not copy primary VPS `.env` or API keys into Git.
3. Do not open broad public ports for Redis, Qdrant, browser helpers, or
   provider-probe services.

## Tracked Assets

- `deploy/jdcloud/deploy_probe_platform.sh`
- `deploy/jdcloud/install_playwright.sh`
- `deploy/jdcloud/lima-probe-browser.service`
- `deploy/jdcloud/lima-probe.service`
- `deploy/jdcloud/lima-probe.timer`
- `scripts/check_jdcloud_node.py` for read-only capacity/service smoke
- supporting optional setup templates under `deploy/jdcloud/`

## Ignored Local Artifacts

The workspace has local JDCloud helpers and generated reports that may contain
passwords or one-off operator state. They are intentionally not tracked.

Examples:

- `deploy/jdcloud/deploy_jd.py`
- `deploy/jdcloud/deploy_via_paramiko.py`
- `deploy/jdcloud/*DEPLOY*.txt`
- `docs/JDCLOUD_*.md`
- `scripts/test_jdcloud_connection.py`
- `scripts/test_redis_from_local.py`

## Credential Policy

- Do not commit SSH passwords, Redis passwords, Grafana admin passwords, API
  tokens, or copied `.env` values.
- Prefer SSH key based deployment.
- If password-based emergency access is needed, keep it in the operator's
  local password manager or an ignored local file.
- Tracked scripts should read runtime secrets from environment variables or
  prompt the operator, not hardcode them.

## Open Operational Questions

- Whether JDCloud should only self-monitor, or also report sanitized probe
  results back to LiMa after the read-only smoke is stable.
- Whether a future `/v1/ops/backends/probe-batch` endpoint is still needed.
  The current untracked prototype is not production-ready because it hardcodes
  authentication and bypasses the existing private API dependency pattern.

## 2026-06-09 Runtime Activation Evidence

- `scripts/check_jdcloud_node.py --json` reached JDCloud with strict host-key
  policy and reported `chat_health_http_code=200`, `prometheus_service=active`,
  `disk_free_mb=41266`, and `mem_available_mb=2308` before activation.
- `lima-probe.timer` was already enabled but inactive; it was started with
  `systemctl start lima-probe.timer` and then reported `active`.
- The next scheduled timer run was reported as
  `Wed 2026-06-10 00:18:10 CST`.
- A manual `systemctl start lima-probe.service` completed successfully with
  `status=0/SUCCESS`; the discovery run reported `37 new, 37 total known`
  and wrote `/opt/lima-probe/data/discoveries.jsonl` plus
  `/opt/lima-probe/data/known_providers.json`.
- Follow-up read-only smoke reported `ok=true`, `chat_health_http_code=200`,
  `lima_probe_timer=active`, `lima_probe_service=inactive`,
  `prometheus_service=active`, `disk_free_mb=41266`, and
  `mem_available_mb=1761`.

Residual risk:

- The local browser render helper on JDCloud is reachable on loopback, but the
  probe journal shows `POST http://127.0.0.1:8092/render` returning `500` for
  several browser-backed discovery URLs. The non-browser discovery path still
  completed successfully, so the next improvement should debug the browser
  helper without exposing port `8092`.

## Latest Hygiene Evidence

- Local JDCloud password helpers were not staged.
- Root `.gitignore` now protects the known JDCloud scratch/report files.
- `.codegraph/daemon.pid` is removed from the Git index and PID files are
  ignored as local runtime state.
