# LiMa Status

> Updated: 2026-05-22
> Active direction: private personal coding assistant.

## Current Summary

| Area | Status | Evidence |
|---|---|---|
| Product direction | Active | Commercial work paused; `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` is the current plan. |
| Coding backend eval | Complete for first pass | 85-candidate smoke, 16-candidate full fixture set, ranking docs and JSON results exist. |
| Coding routing | Active | `code_orchestrator.py`, `routing_engine.py`, and `router_v3.py` route coding traffic by evidence-backed tiers. |
| IDE context preflight | Deployed | `lima_context.py` injects request-local context into coding and Anthropic tool paths. |
| Claude Code tool path | Deployed | `/v1/messages` tool smoke returned `tool_use` after speed and context changes. |
| VPS safety baseline | Retained | HTTPS, headers, internal port blocking, backup practices. |

## Latest Routing Facts

- Full coding fixture passers include `github_gpt4o`, `github_gpt4o_mini`, and `or_gptoss_120b`.
- `scnet_large_ds_flash` passed local coding fixtures, but its VPS local proxy `4505` is currently not running; it is now late fallback instead of production-first.
- Fast coding capacity includes `cerebras_gptoss`, `groq_gptoss`, `mistral_small`, and simple-case `groq_gptoss_20b`.
- Working VPS free SCNet direct models are now active fallback capacity:
  - `scnet_ds_flash`
  - `scnet_ds_pro`
  - `scnet_qwen235b`
  - `scnet_qwen30b`
- Kimi is only partially live:
  - `cf_kimi_k26` works but is slow.
  - local `kimi`, `kimi_thinking`, and `kimi_search` need VPS proxy `4504`.
  - `stock_kimi_k2` did not return a valid smoke response.

See `docs/FREE_MODEL_ROUTING_STATUS.md` and `docs/LIMA_MEMORY.md`.

## Production Topology

| Component | Status |
|---|---|
| nginx HTTPS edge | Running |
| `chat.donglicao.com` | Private chat plus LiMa `/v1/*` entry |
| `api.donglicao.com` | Existing New API entry retained |
| `lima-router` | systemd service, localhost `8080` |
| New API | localhost `3003` |
| Voice gateway | localhost `8091`, not main product direction |

## Active Code

| File | Role |
|---|---|
| `server.py` | OpenAI/Anthropic protocol boundary |
| `routing_engine.py` | Scenario classification and route execution |
| `router_v3.py` | Backend pools |
| `code_orchestrator.py` | Coding tier logic and quality loop |
| `lima_context.py` | Context preflight |
| `http_caller.py` | Backend HTTP transport |
| `backends.py` | Backend inventory |

## Verification Record

Latest completed context-preflight verification:

```text
python -m py_compile lima_context.py code_orchestrator.py server.py routing_engine.py router_v3.py
python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py
70 passed
```

Latest free-model VPS smoke:

- SCNet direct working: `scnet_ds_flash`, `scnet_ds_pro`, `scnet_qwen235b`, `scnet_qwen30b`.
- Kimi working but slow: `cf_kimi_k26`.
- Proxy-backed or invalid in smoke: `scnet_large_*`, local `kimi*`, `stock_kimi_k2`, `scnet_minimax`.

Latest free-model routing deployment:

- Backup: `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- Local tests: `71 passed`.
- VPS `/health`: 200.
- Public coding smoke: 200 in 4585ms.
- Public Anthropic tool smoke: 200 in 672ms with `stop_reason=tool_use`.

Latest SCNet/Kimi first-tier eval:

- Promoted to first-tier coding: `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`.
- Not promoted: `cf_kimi_k26`, `stock_kimi_k2`, local `kimi*`, `scnet_large_*`, `scnet_minimax`.
- Backup: `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Public coding smoke: 200 in 3347ms.

## Paused Or Removed

- Payment and commercial platform docs.
- Billing/quota/training experiments not needed for the current personal assistant direction.
- Large reference repos and one-off debug scripts stay local unless explicitly curated.

## Next Waiting Point

The repo documentation, memory, and GitHub snapshot should be updated first. After that, wait for the user's next task.
