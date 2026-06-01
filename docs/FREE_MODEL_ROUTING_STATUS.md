> ⚠️ 2026-06-01 起已过时。LOCAL_ONLY_BACKENDS 已清空，所有后端云端化。当前状态见 STATUS.md

# Free Model Routing Status

> Updated: 2026-05-26
> Scope: SCNet and Kimi-family free or near-free backends in LiMa.

## 2026-05-26 Re-eval C（11 backends 全量）

Command: `eval_coding_backends.py` × 11 × 3 cases（~3.3min）。

| Backend | Passes | Avg Score | Avg Latency | Decision |
|---|---:|---:|---:|---|
| `scnet_large_ds_pro` | 3/3 | 100 | 1232ms | Local 4505 最快 pro |
| `scnet_qwen30b` / `scnet_large_ds_flash` / `scnet_qwen235b` / `scnet_ds_flash` | 3/3 | 100 | 1.3–2.0s | First tier |
| `scnet_ds_pro` | **3/3** | 100 | 6451ms | Deep tier（timeout 90 + empty guard） |
| `cf_kimi_k26` / `kimi_search` / `kimi_thinking` | 3/3 | 100 | 4.8–27s | Coding 候选 |
| `kimi` | **3/3** | 100 | ~17s | timeout 45s；见 `kimi_eval_timeout45.json` |
| `stock_kimi_k2` | 0/3 | 0 | — | Inactive |

Raw: `data/scnet_kimi_eval_20260526_full.json`、`docs/CODING_BACKEND_RANKING.md`。

---

## 2026-05-26 Re-eval B（JSON 围栏 + scnet_ds_pro timeout）

Command: `scripts/eval_coding_backends.py` — Kimi 三模式 + `scnet_ds_pro`（post-fix）。

| Backend | Passes | Avg Score | Avg Latency | Decision |
|---|---:|---:|---:|---|
| `kimi` / `kimi_thinking` / `kimi_search` | **3/3** | 100 | 3–11s | **Coding 候选**（JSON 围栏解析已修复） |
| `scnet_ds_pro` | **3/3** | 100 | 9–16s（复测；直连偶发空响应→`http_sync` 空体 fail-fast） | 恢复 first-tier 深推理候选（仍慢于 flash） |

Raw: `data/scnet_kimi_eval_20260526b.json`、`data/scnet_ds_pro_eval_retry.json`。

---

## 2026-05-26 Re-eval（local Windows proxy）

Command: `scripts/eval_coding_backends.py` on 11 SCNet/Kimi backends × 3 coding cases.

| Backend | Passes | Avg Score | Avg Latency | Decision |
|---|---:|---:|---:|---|
| `scnet_large_ds_flash` | 3/3 | 100 | **1199ms** | **Fastest** first-tier via `localhost:4505` |
| `scnet_qwen30b` | 3/3 | 100 | 1814ms | First tier (VPS direct) |
| `scnet_ds_flash` | 3/3 | 100 | 2205ms | First tier |
| `scnet_qwen235b` | 3/3 | 100 | 2388ms | First tier |
| `scnet_large_ds_pro` | 3/3 | 100 | 75046ms | Local deep only (too slow for hot path) |
| `kimi` / `kimi_thinking` / `kimi_search` | 2/3 | 80 | 4–7s | **Superseded** —见 Re-eval B **3/3** |
| `cf_kimi_k26` | 1/3 | 48 | 6776ms | Fallback only |
| `scnet_ds_pro` | 0/3 | 0 | timeout/cooldown | **Superseded** —timeout 90 + 空响应 guard；复测 **3/3** |
| `stock_kimi_k2` | 0/3 | 0 | invalid/cooldown | Inactive |

Raw: `data/scnet_kimi_eval_20260526.json`, `docs/CODING_BACKEND_RANKING.md`.

**Kimi 状态变化：** 2026-05-22 记录 `chat.anonymous_usage_exceeded`；**2026-05-26 重评已恢复 chat**，仍不宜进 strict JSON / 第一 coding 池。

---

## Current Answer

SCNet direct models are strong enough to enter the first-tier coding route.

LiMa now promotes the VPS-working direct SCNet models into the first tier for coding. The Windows local proxy path is also confirmed: SCNet-large runs on `D:\ollama_server` port `4505` and works through the local LiMa router. Kimi port `4504` is running, but its chat call currently fails because the Kimi login state has fallen back to anonymous quota.

## First-Tier Fixture Evidence

VPS eval date: 2026-05-22.

| Backend | Passes | Avg Score | Avg Latency | Decision |
|---|---:|---:|---:|---|
| `scnet_ds_flash` | 3/3 | 100 | 3330ms | First tier |
| `scnet_qwen235b` | 3/3 | 100 | 4004ms | First tier |
| `scnet_qwen30b` | 3/3 | 91 | 2713ms | First tier |
| `scnet_ds_pro` | 3/3 | 91 | 4571ms | First tier, behind faster SCNet models |
| `cf_kimi_k26` | 1/3 | 48 | 7844ms | Fallback only |
| `scnet_minimax` | 0/3 | 0 | 10145ms | Inactive, timeout |
| `scnet_large_ds_flash` | 3/3 local route eval | 100 | 987ms | Strong local/FRP candidate; promote only with local-proxy topology guard |
| `scnet_large_ds_pro` | 3/3 local route eval | 100 | 3899ms | Strong local/FRP candidate, slower than flash |
| `stock_kimi_k2` | 0/3 | 0 | 525ms | Inactive, invalid response |
| `kimi` | auth/quota fail | 0 | 0ms | Port `4504` runs, but chat returns `chat.anonymous_usage_exceeded` |
| `kimi_thinking` | auth/quota fail | 0 | 0ms | Port `4504` runs, blocked by Kimi login state |
| `kimi_search` | auth/quota fail | 0 | 0ms | Port `4504` runs, blocked by Kimi login state |

Raw summary: `data/free_model_first_tier_eval.json`.

## VPS Smoke Evidence

Smoke prompt: `Say OK only.`

| Backend | Status | Latency | Routing Decision |
|---|---:|---:|---|
| `scnet_ds_flash` | OK | 2904ms | Active free fallback for coding/chat. |
| `scnet_ds_pro` | OK | 26496ms | Strong/deep fallback only because it is slow. |
| `scnet_qwen235b` | OK | 2110ms | Active free fallback for coding/chat. |
| `scnet_qwen30b` | OK | 1727ms | Active fast/chat fallback. |
| `scnet_minimax` | Timeout | 30742ms | Registered, not active in default pools. |
| `scnet_large_ds_flash` | Local route eval OK | 987ms avg | Registered; Windows local proxy `4505` is coding-fixture compatible. |
| `scnet_large_ds_pro` | Local route eval OK | 3899ms avg | Registered; strong but slower than `flash`. |
| `cf_kimi_k26` | OK | 9987ms | Active chat fallback; coding fallback only after stronger models. |
| `stock_kimi_k2` | Invalid response | 2070ms | Registered, not active in default pools. |
| `kimi` | Auth/quota fail | 0ms | Registered; Windows local proxy `4504` runs, but Kimi session needs re-login. |
| `kimi_thinking` | Auth/quota fail | 0ms | Registered; Windows local proxy `4504` runs, but Kimi session needs re-login. |
| `kimi_search` | Auth/quota fail | 0ms | Registered; Windows local proxy `4504` runs, but Kimi session needs re-login. |

## Code Changes

| File | Update |
|---|---|
| `code_orchestrator.py` | Promoted `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, and `scnet_ds_pro` into first-tier coding pools. |
| `router_v3.py` | Promoted VPS-working SCNet direct models to the front of IDE/chat/code/chat_fast pools. |
| `test_routing_engine.py` | Added regression coverage for SCNet first-tier ordering and Kimi fallback placement. |

## DuckAI Local Admission Evidence

Local eval date: 2026-05-22. Command output is recorded in `data/ddg_route_admission_eval.json` and `docs/DDG_ROUTE_ADMISSION.md`.

| Backend | Passes | Avg Score | Avg Latency | Decision |
|---|---:|---:|---:|---|
| `ddg_gpt4o_mini` | 3/3 | 100 | 3022ms | Late local fallback; not first tier. |
| `ddg_gpt5_mini` | 3/3 | 100 | 3626ms | Late local fallback; not first tier. |
| `ddg_claude_haiku_45` | 2/3 | 58 | 2358ms | Chat-like fallback only; failed strict JSON output. |
| `ddg_tinfoil_gptoss_120b` | 0/3 | 0 | 89ms | Inactive; upstream 500 and cooldown. |

## Deployment Evidence

- Local tests after route change: `71 passed in 0.52s`.
- VPS backup: `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- Remote compile passed for the changed routing files.
- VPS local `/health` returned 200 after restart recovery.
- Public coding smoke returned 200 in 4585ms.
- Public Anthropic tool smoke returned 200 in 672ms with `stop_reason=tool_use`.

## First-Tier Deployment Evidence

- Local tests after first-tier promotion: `71 passed in 0.59s`.
- VPS backup: `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Remote compile passed for `server.py`, `routing_engine.py`, `code_orchestrator.py`, and `router_v3.py`.
- VPS local `/health` returned 200 after restart.
- VPS route-order smoke confirmed coding selection starts with `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, then `github_gpt4o`.
- Public coding smoke returned 200 in 3347ms.

## Policy

- Coding primary remains evidence-driven: SCNet direct models now lead because they passed production VPS fixtures.
- `scnet_ds_flash`, `scnet_qwen235b`, and `scnet_qwen30b` are first-tier coding candidates.
- `scnet_ds_pro` is also first-tier eligible, but ordered after faster SCNet models due to latency/format variance.
- `cf_kimi_k26` is usable but slow and verbose, so it is kept for fallback instead of first-tier IDE coding.
- Local proxy models must be verified through the Windows LiMa router path, not by checking VPS `localhost:4504/4505`.
- Kimi local failures should be treated as `manual_refresh_required` or `quota_exhausted`, not retried repeatedly in the hot path.
- DuckAI `ddg_gpt4o_mini` and `ddg_gpt5_mini` are admitted only as late local fallback until the public tunnel is repaired and longer stability runs pass.
- SCNet-large is strong on the Windows local route, but must not be promoted on a VPS process that cannot reach Windows `localhost:4505`.
- Future no-login web AI adapters must stay out of first-tier coding until they pass the admission rules in `docs/FREE_WEB_AI_EXPANSION_PLAN.md`.
- `health_tracker.record_failure` now accepts `error_text`, classifies Kimi anonymous quota/session failures, and stores a backend state for later route skipping/scoring.

## Next Verification

When proxy services are intentionally started:

```bash
curl -sS http://127.0.0.1:4504/v1/models
curl -sS http://127.0.0.1:4505/v1/chat/completions
curl -sS http://127.0.0.1:8080/v1/chat/completions
```

Then re-run the coding eval against:

- `kimi`
- `kimi_thinking`
- `kimi_search`
- `scnet_large_ds_flash`
- `scnet_large_ds_pro`
