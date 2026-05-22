# Free Model Routing Status

> Updated: 2026-05-22
> Scope: SCNet and Kimi-family free or near-free backends in LiMa.

## Current Answer

Not every registered free model should be used as a primary backend.

LiMa now keeps the working free models in active routing pools, but only promotes the ones that passed VPS smoke into normal fallback order. Free models that require local browser/proxy services stay registered in `backends.py`, but are not treated as dependable primary capacity until those services are running on the VPS.

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
| `code_orchestrator.py` | Added VPS-working SCNet models to coding pools after proven coding winners; moved local-proxy SCNet variants to late fallback. |
| `router_v3.py` | Added VPS-working SCNet models to IDE/chat/code/chat_fast pools; kept `cf_kimi_k26` active but not primary for coding. |
| `test_routing_engine.py` | Added regression coverage that active pools include VPS-working free SCNet models and CF Kimi. |

## Deployment Evidence

- Local tests after route change: `71 passed in 0.52s`.
- VPS backup: `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- Remote compile passed for the changed routing files.
- VPS local `/health` returned 200 after restart recovery.
- Public coding smoke returned 200 in 4585ms.
- Public Anthropic tool smoke returned 200 in 672ms with `stop_reason=tool_use`.

## Policy

- Coding primary remains evidence-driven: GitHub, Cerebras, Groq, and Mistral winners stay ahead where they passed the full coding fixture.
- Free SCNet direct models are now used as fallback capacity because they work from the VPS.
- `scnet_ds_pro` is usable but slow, so it belongs in strong/deep fallback only.
- `cf_kimi_k26` is usable but slow and verbose, so it is kept for chat/fallback instead of low-latency IDE default.
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
