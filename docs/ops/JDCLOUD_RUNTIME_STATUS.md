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

## Tracked Assets

- `deploy/jdcloud/deploy_probe_platform.sh`
- `deploy/jdcloud/install_playwright.sh`
- `deploy/jdcloud/lima-probe-browser.service`
- `deploy/jdcloud/lima-probe.service`
- `deploy/jdcloud/lima-probe.timer`
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

- Whether JDCloud can reliably reach the primary Aliyun VPS over the intended
  network path.
- Whether JDCloud should only self-monitor, or also report sanitized probe
  results back to LiMa.
- Whether a future `/v1/ops/backends/probe-batch` endpoint is still needed.
  The current untracked prototype is not production-ready because it hardcodes
  authentication and bypasses the existing private API dependency pattern.

## Latest Hygiene Evidence

- Local JDCloud password helpers were not staged.
- Root `.gitignore` now protects the known JDCloud scratch/report files.
- `.codegraph/daemon.pid` is removed from the Git index and PID files are
  ignored as local runtime state.
