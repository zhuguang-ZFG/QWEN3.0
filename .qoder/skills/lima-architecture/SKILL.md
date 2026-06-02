---
name: lima-architecture
description: LiMa project architecture navigation and module discovery. Maps the full request pipeline, module boundaries, dependency injection, protocol handling (OpenAI/Anthropic), routing engine layers, and key file locations. Use when understanding code flow, locating modules, tracing request paths, or onboarding to the codebase.
---

# LiMa Architecture Navigator

## Tech Stack

- Python 3.10, FastAPI, uvicorn, httpx
- SQLite (sessions), Redis (optional), pybreaker
- Port 8080, single-process async

## Request Pipeline

```
Client (OpenAI/Anthropic protocol)
  → server.py (FastAPI app + BodySizeLimitMiddleware)
  → routes/chat_endpoints.py (protocol detection + auth)
    ├─ /v1/chat/completions → OpenAI path
    └─ /v1/messages         → Anthropic path
  → routes/chat_preflight.py (validation)
  → routing_engine.route()
      ├─ identity_guard       (self-identification)
      ├─ semantic_cache       (temperature=0 cache)
      ├─ routing_classifier   (intent + scenario)
      ├─ context_pipeline     (retrieval, web search, code context)
      ├─ skills_injector      (backend-aware skill injection)
      ├─ code_orchestrator    (coding scenario handling)
      ├─ routing_selector     (backend selection: health, sticky, budget)
      ├─ routing_executor     (execute with fallback chain)
      └─ speculative          (parallel speculative calls)
  → http_caller → http_sync/http_async/http_stream
  → route_post_process.py + response_cleaner.py
  → routes/chat_post_closeout.py (memory, observability)
```

## Protocol Handling

| Protocol | Entry Point | Tool Format | Streaming |
|----------|-------------|-------------|-----------|
| OpenAI | `/v1/chat/completions` | `tool_calls[]` in message | SSE `data: {...}` |
| Anthropic | `/v1/messages` | `tool_use` content block | SSE `event: ...` |

Key converter: `converters/anthropic_format.py` handles Anthropic↔OpenAI format translation including `tool_choice`.

## Module Map

### Core Routing

| File | Role |
|------|------|
| `routing_engine.py` | Authoritative routing entry (5-layer pipeline) |
| `routing_classifier.py` | Classifies intent (coding/chat/translation/vision/etc.) |
| `routing_selector.py` | Selects best backend (health score, sticky, budget) |
| `routing_executor.py` | Executes call with fallback chain |
| `route_scorer.py` | Backend scoring weights |
| `route_post_process.py` | Response post-processing |
| `smart_router.py` | V3 compat facade — delegates to `routing_engine` |

### Backend Management

| File | Role |
|------|------|
| `backends_registry.py` | Dict of all 180+ backend configs (name → URL/model/key) |
| `backends_constants.py` | Capability lists: `CODE_CAPABLE_BACKENDS`, `VISION_BACKENDS`, etc. |
| `backends.py` | Facade re-exporting both registries |
| `health_tracker.py` | Health state tracking (prefer over `router_circuit_breaker.py`) |
| `sticky_session.py` | Per-user sticky backend assignment |

### HTTP Transport

| File | Role |
|------|------|
| `http_caller.py` | Thin facade over transport modules |
| `http_async.py` | Async HTTP calls |
| `http_sync.py` | Sync HTTP calls |
| `http_stream.py` | Streaming HTTP (SSE) |
| `http_request_builder.py` | Request construction |
| `http_response.py` | Response normalization |
| `http_errors.py` | Error classification |

### Tool Calling Pipeline

| File | Role |
|------|------|
| `routes/tool_forward.py` | Sync tool forwarding (Anthropic native → OpenAI backends) |
| `routes/tool_forward_stream.py` | Streaming tool forwarding (Tier1/Tier2) |
| `text_tool_extractor.py` | Extract tool_calls from plain text responses |
| `converters/anthropic_format.py` | Protocol conversion (Anthropic ↔ OpenAI) |

Tier1 = OpenAI native `tool_calls` passthrough.
Tier2 = Anthropic-native tools forwarded to capable backends.

### Context & Memory

| File | Role |
|------|------|
| `context_pipeline/` | Retrieval, web search, code context, enrichment, compression |
| `session_memory/` | Split: db/crud/promote/admin |
| `code_orchestrator.py` | Coding scenario handling |
| `code_orchestrator_context.py` | Code context injection |
| `skills_injector.py` | Backend-aware skill injection |

### Agent Runtime

| File | Role |
|------|------|
| `agent_runtime/orchestrator.py` | Facade for task queue + worker |
| `agent_runtime/executor.py` | Task execution |
| `agent_runtime/events.py` | Event system |
| `agent_contracts/` | Task contracts |
| `agent_roles/` | Role definitions |
| `agent_eval/` | Evaluation scoring |

### Infrastructure

| File | Role |
|------|------|
| `server.py` | FastAPI entry, wires deps via DI |
| `server_bootstrap.py` | Creates runtime state |
| `server_lifespan.py` | Async lifespan (probe loop, Telegram, device gateway) |
| `rate_limiter.py` | Request rate limiting |
| `budget_manager.py` | Cost/budget tracking |
| `semantic_cache.py` | Semantic dedup cache |

### External Gateways

| File | Role |
|------|------|
| `routes/telegram*.py` | Telegram bot commands and dispatch |
| `device_gateway/` | ESP32/hardware WebSocket + MQTT |
| `channel_gateway/` | Multi-channel message routing |
| `reverse_gateway/` | Reverse-engineered free AI platforms |
| `lima_mcp/` | Model Context Protocol server |

## Dependency Injection Pattern

`server.py` uses explicit DI: modules expose `inject_state()` / `inject_deps()`.
State is created in `server_bootstrap.create_runtime_state()` and injected at startup.
**New modules must avoid global mutable state — use inject pattern.**

## Facade Pattern Warning

Several modules are thin re-exports: `backends.py`, `http_caller.py`, `smart_router.py`.
**Check before adding logic** — these files should stay as facades.

## Key Config Files

| File | Purpose |
|------|---------|
| `.env` | Secrets + feature flags (never commit) |
| `backends_registry.py` | Backend definitions |
| `backends_constants.py` | Capability classifications |
| `ruff.toml` | Linting config (py310, line-length 120) |
| `pyrightconfig.json` | Type checking (basic mode) |
| `pytest.ini` | Test config (asyncio_mode=auto, testpaths=tests) |
