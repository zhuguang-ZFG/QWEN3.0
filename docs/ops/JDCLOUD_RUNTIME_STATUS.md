# JDCloud Runtime Status

> Updated: 2026-06-27
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
| Role | Secondary provider-probe / monitoring node + probe result ingress source |
| Primary API replacement | No |
| Credential storage | Outside Git only |
| Tracked deploy assets | `deploy/jdcloud/` shell and systemd templates |
| Local scratch policy | Ignored by exact `.gitignore` rules |
| Latest read-only smoke | `ok=true`, `chat_health_http_code=200`, `lima_probe_timer=active` |
| Probe push timer | `lima-probe-push.timer` active, last push `recorded=39` |

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
- `deploy/jdcloud/push_probe_results.py`
- `deploy/jdcloud/push_probe_results_utils.py`
- `deploy/jdcloud/lima-probe-push.service`
- `deploy/jdcloud/lima-probe-push.timer`
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

## Phase 1 实施证据（2026-06-27）

按 `docs/superpowers/specs/2026-06-28-jdcloud-utilization-plan.md` 完成
probe 结果回写与异地观测：

- **LiMa 接收端点**：
  - `POST /admin/api/probe/ingress` 已部署到主 VPS，使用独立
    `LIMA_PROBE_INGRESS_TOKEN`，默认关闭。
  - `GET /admin/api/probe/jdcloud` 已可通过 admin 认证查询京东云 probe 快照。
- **京东云推送**：
  - 新增 `deploy/jdcloud/push_probe_results.py` + `push_probe_results_utils.py`
    读取 `/opt/lima-probe/data/known_providers.json`、`discoveries.jsonl` 与
    `stability.json`，生成脱敏 payload。
  - 新增 `lima-probe-push.service` / `lima-probe-push.timer`，每 5 分钟推送一次。
  - 推送脚本以专用 `lima-probe` 用户运行，token 通过
    `/opt/lima-probe/.probe-ingress.env` 注入，不进入 Git。
- **网络 bypass**：由于 `chat.donglicao.com` 经 Cloudflare 代理时返回 1010，
  京东云节点 `/etc/hosts` 将 `chat.donglicao.com` 指向主 VPS 源站
  `47.112.162.80`，使 HTTPS 请求绕过 Cloudflare 直接到达 nginx。
- **验证**：
  - 主 VPS `POST /admin/api/probe/ingress` 返回 `{"recorded":1}`。
  - 京东云 `systemctl start lima-probe-push.service` 日志显示
    `probe push: status=200 recorded=39`。
  - 主 VPS `GET /admin/api/probe/jdcloud` 返回 39 条京东云 probe 记录。

## Phase D 资源盘点（2026-06-27）

为评估 Phase 2（分担低价/免费后端流量）可行性，对京东云节点进行资源审计：

| 资源 | 值 | 评估 |
|---|---|---|
| CPU | 2 vCPU（Intel Xeon E5-2683 v4 @ 2.10GHz）| 负载极低（loadavg ~0.02），有充足算力 |
| 内存 | 总计 3.9 GB / 可用 558 MB | 已运行 new-api、MySQL、Redis、Prometheus、browser helper；可用内存偏紧，新增 worker 需谨慎 |
| 磁盘 | 59 GB 总量 / 26 GB 可用 | 充足 |
| 网络 | 公网 IP `117.72.118.95`、Tailscale `100.85.114.65` | 具备出站能力；443/80 由 nginx 占用 |
| 主要服务 | new-api:3000、qwen2api:7862、MySQL:3306、Redis:6379、Prometheus、browser:8092 | 端口占用较多，新增公开入口需避免冲突 |
| Probe 推送 | `lima-probe-push.timer` active | Phase 1 运行正常 |

**结论**：京东云当前负载轻，可作为低价/免费后代的出站代理；但内存余量仅约 500MB，
Phase 2 设计应采用轻量反向代理/Worker 模式，不常驻重负载服务，且需要严格的内存与
连接数上限。

## Latest Hygiene Evidence

- Local JDCloud password helpers were not staged.
- Root `.gitignore` now protects the known JDCloud scratch/report files.
- `.codegraph/daemon.pid` is removed from the Git index and PID files are
  ignored as local runtime state.
