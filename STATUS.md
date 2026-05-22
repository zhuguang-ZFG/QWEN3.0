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
- `scnet_large_ds_flash` passed local coding fixtures. Its proxy is Windows-local on `D:\ollama_server:4505`; VPS `localhost:4505` is the wrong health signal for the current FRP architecture.
- Fast coding capacity includes `cerebras_gptoss`, `groq_gptoss`, `mistral_small`, and simple-case `groq_gptoss_20b`.
- Working VPS free SCNet direct models are now active fallback capacity:
  - `scnet_ds_flash`
  - `scnet_ds_pro`
  - `scnet_qwen235b`
  - `scnet_qwen30b`
- Kimi is only partially live:
  - `cf_kimi_k26` works but is slow.
  - local `kimi`, `kimi_thinking`, and `kimi_search` run behind Windows-local port `4504`, but current chat calls fail with `chat.anonymous_usage_exceeded`.
  - `stock_kimi_k2` did not return a valid smoke response.

## Public Endpoint State

| Endpoint | Status | Intended Use |
|---|---|---|
| `https://chat.donglicao.com/v1` | Working private HTTPS path | Real IDE/agent clients when HTTPS is preferred. |
| `http://47.112.162.80:8088/v1` | Working FRP path to Windows local router | Direct validation of local-router plus Windows proxy backends. |
| `https://api.donglicao.com/v1` | New API gateway retained | Requires a real New API token; `lima-local` is not valid there. |

Known IDE config:

```text
Base URL: https://chat.donglicao.com/v1
Alt URL:  http://47.112.162.80:8088/v1
API key:  lima-local
Model:    lima-1.3
```

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

## Windows FRP Topology

The FRP path is closed and should be treated as production-relevant for local free web/proxy backends:

```text
IDE/client
  -> http://47.112.162.80:8088/v1
  -> VPS frps 8088
  -> Windows frpc redcode-api
  -> Windows LiMa API 127.0.0.1:8080
  -> Windows local providers on 4504/4505 when selected
```

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

Latest documentation/FRP verification:

- `git diff --check`: passed, with line-ending warnings only.
- `pytest --ignore=active_model`: `66 passed, 5 skipped` for the core routing/HTTP/streaming/eval/context suite.
- `http://47.112.162.80:8088/health`: 200.
- `http://47.112.162.80:8088/v1/models`: 200 with `lima-local`.
- `http://47.112.162.80:8088/v1/chat/completions`: 200, routed through LiMa.
- Caveat: `D:\GIT\active_model` is a stale junction to a deleted temp directory, so plain pytest collection fails unless ignored or the junction is cleaned.

## Paused Or Removed

- Payment and commercial platform docs.
- Billing/quota/training experiments not needed for the current personal assistant direction.
- Large reference repos and one-off debug scripts stay local unless explicitly curated.

## Current Roadmap

1. Expand no-login web AI candidates conservatively: sandbox registry and reachability probe now exist; DuckAI is the first high-confidence candidate.
2. Improve backend stability: `health_tracker.py` now classifies token/session/quota/rate-limit/timeout failure states.
3. Optimize free-backend routing next: quota-aware weighted routing, latency buckets, backend quality score decay, and cheap-first/simple-task policy.

Source-of-truth docs for the next phase:

- `docs/FREE_WEB_AI_EXPANSION_PLAN.md`
- `docs/superpowers/plans/2026-05-22-free-web-ai-stability-routing.md`
- `docs/DOCUMENTATION_STATUS.md`
- `docs/LIMA_MEMORY.md`

Latest free web AI sandbox state:

- Registry: `data/free_web_ai_candidates.json`.
- Probe results: `data/free_web_ai_probe_results.json`.
- Reachability probe found 6/6 candidate pages return HTTP 200.
- Important boundary: this is page reachability only, not model-backend admission.
- Current branch verification: `72 passed, 5 skipped` with `pytest --ignore=active_model`; JSON registry/results validate; FRP `/health` returned 200.
