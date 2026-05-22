# Free Model Routing Status

> Updated: 2026-05-22
> Scope: SCNet and Kimi-family free or near-free backends in LiMa.

## Current Answer

SCNet direct models are strong enough to enter the first-tier coding route.

LiMa now promotes the VPS-working direct SCNet models into the first tier for coding. Kimi-family models do not currently meet first-tier criteria: CF Kimi is reachable but too verbose/slow for strict coding fixtures, and local Kimi proxy models are not running on the VPS.

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
| `scnet_large_ds_flash` | 0/3 | 0 | 0ms | Inactive until proxy `4505` runs |
| `scnet_large_ds_pro` | 0/3 | 0 | 0ms | Inactive until proxy `4505` runs |
| `stock_kimi_k2` | 0/3 | 0 | 525ms | Inactive, invalid response |
| `kimi` | 0/3 | 0 | 0ms | Inactive until proxy `4504` runs |
| `kimi_thinking` | 0/3 | 0 | 0ms | Inactive until proxy `4504` runs |
| `kimi_search` | 0/3 | 0 | 0ms | Inactive until proxy `4504` runs |

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
| `scnet_large_ds_flash` | Connection refused | 6ms | Registered, late fallback only; VPS local proxy `4505` is not running. |
| `scnet_large_ds_pro` | Connection refused | 0ms | Registered, late fallback only; VPS local proxy `4505` is not running. |
| `cf_kimi_k26` | OK | 9987ms | Active chat fallback; coding fallback only after stronger models. |
| `stock_kimi_k2` | Invalid response | 2070ms | Registered, not active in default pools. |
| `kimi` | Connection refused | 0ms | Registered, inactive until VPS local proxy `4504` runs. |
| `kimi_thinking` | Connection refused | 0ms | Registered, inactive until VPS local proxy `4504` runs. |
| `kimi_search` | Connection refused | 0ms | Registered, inactive until VPS local proxy `4504` runs. |

## Code Changes

| File | Update |
|---|---|
| `code_orchestrator.py` | Promoted `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, and `scnet_ds_pro` into first-tier coding pools. |
| `router_v3.py` | Promoted VPS-working SCNet direct models to the front of IDE/chat/code/chat_fast pools. |
| `test_routing_engine.py` | Added regression coverage for SCNet first-tier ordering and Kimi fallback placement. |

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
- Local proxy models are not considered live until the corresponding VPS proxy service is verified.

## Next Verification

When proxy services are intentionally started:

```bash
curl -sS http://127.0.0.1:4504/v1/chat/completions
curl -sS http://127.0.0.1:4505/v1/chat/completions
```

Then re-run the coding eval against:

- `kimi`
- `kimi_thinking`
- `kimi_search`
- `scnet_large_ds_flash`
- `scnet_large_ds_pro`
