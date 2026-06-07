# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

For full history, read `STATUS.md`; for pipeline ownership, read `docs/REQUEST_PIPELINE_AUTHORITY.md`; for product scope, read `docs/PRODUCT_DEFINITION.md`.

## Repo Identity

- LiMa is a **personal AI coding assistant backend**, not a commercial platform. Do not reintroduce payment, public registration, customer billing, or commercial dashboard work unless explicitly requested.
- Runtime: Python 3.10 + FastAPI on port `8080`; primary client is **OpenCode** (deep integration).
- OpenAI-compatible at `/v1/chat/completions`, Anthropic-compatible at `/v1/messages`.
- Backend inventory is cloud-first: 184 providers in `backends_registry.py` + `backends_constants.py`. `LOCAL_ONLY_BACKENDS` is intentionally empty.
- **IDE Support**: Deep integration with OpenCode only. Other IDEs (Cursor, Continue.dev, VS Code) can use the OpenAI-compatible API but without specialized optimizations.

## Commands

```text
# Install
pip install -r requirements_server.txt

# Run server (local)
python server.py
python -m uvicorn server:app --host 0.0.0.0 --port 8080

# Test (use project venv on Windows: .venv310\Scripts\python.exe)
pytest --tb=short -q                                          # full suite
pytest tests/ -q --ignore=tests/test_ci_gates.py              # without CI gates
pytest tests/test_routing_engine.py -v                        # single file
pytest tests/test_http_caller_concurrency.py::test_concurrent_calls -v  # single test
pytest -m "not rag_gate"                                      # skip offline RAG eval

# Lint / Format / Type
ruff check .                  # lint (Python 3.10, line 120, high-signal rules only)
ruff format --check           # format check
ruff format .                 # format fix
pyright                       # type check (local only, not in CI)

# Docker
docker compose build          # also starts SearXNG on host 8081
docker compose up -d
docker compose down

# Smoke (after server start)
curl -sf http://127.0.0.1:8080/health
curl -sf http://127.0.0.1:8080/v1/models | python -m json.tool

# Deploy
python scripts/deploy_unified.py          # automated VPS deploy
python scripts/deploy_vps_bundle.py       # VPS bundle
python scripts/eval_coding_backends.py    # run eval + refresh scores/tiers
python scripts/build_coding_tiers_from_scores.py  # rebuild tiers from scores
python scripts/repo_stats.py              # refresh repo stats
```

**PowerShell note**: use `;` or `if ($?) { ... }`; do not write Unix-style `&&` chains.

### Makefile Shortcuts

```text
make install     # pip install -r requirements_server.txt
make test        # pytest --tb=short -q
make lint        # ruff check . + ruff format --check
make format      # ruff format .
make type-check  # pyright
make serve       # uvicorn --reload (dev server, hot-reload)
make deploy      # python scripts/deploy_unified.py
make smoke-test  # health + models endpoint check
make clean       # remove __pycache__, .pytest_cache, .ruff_cache, *.pyc
```

## Test And CI Facts

- `pytest.ini`: `testpaths = tests`, `pythonpath = .`, `asyncio_mode = auto`. Root-level `test_*.py` files are **not** in the default pytest suite.
- CI (`.github/workflows/test.yml`): `ruff check .` → `bandit -r agent_runtime/ routes/ -ll` → `pytest --tb=short -q`.
- `pyrightconfig.json` checks selected production paths (`routes/`, `routing_engine.py`, `server.py`, etc.) and excludes `tests`, `scripts`, `data`, `deepcode-cli`.
- Ruff rules: `E9, F821-F823, B005, B011, B012, B905, S507, S110, E722, I (isort), UP006/UP007/UP035 (pyupgrade), SIM105/SIM117/SIM118, RUF005/RUF010/RUF100`. Facade modules (`http_caller.py`, `backends.py`, `smart_router.py`, `routing_engine.py`) have `F401` ignored.

## Production Request Path

The live chat pipeline is **explicit and layered** — no single `factory.build_default_pipeline()` owns it:

```
server.py
  → routes/chat_endpoints.py / routes/anthropic_messages_handler.py  [protocol]
  → routes/chat_preflight.py + server_context.py                       [preflight]
  → routing_engine.route()                                             [routing authority]
  → http_caller → http_sync / http_async / http_stream                 [HTTP transport]
  → route_post_process.py / response_cleaner.py                        [post-process]
  → routes/chat_post_closeout.py                                       [memory + metrics]
```

- `routing_engine.route()` is the **backend-selection authority**: classify → select → inject → execute → respond.
- `context_pipeline.factory.build_default_pipeline()` is a **lab/test harness**, not the production owner.
- `routes/route_registry.py` centrally mounts all routers via `RouteRegistryDeps`; `server.py` wires dependencies with `inject_state()` / `inject_deps()`, not FastAPI `Depends`.
- Streaming is handled outside `routing_engine`: `routes/chat_stream.py`, `routes/opencode_direct_stream.py`, `streaming.py`, `streaming_bridge.py`.

## Architecture — Routing Engine 5 Layers

`routing_engine.py` (~400 lines) is the unified routing entry point, replacing `smart_router` + `v3_integration` + `router_v3`:

| Layer | Function | Module |
|-------|----------|--------|
| 1. Classify | Request type: `ide` / `chat` / `vision` / `image` | `routing_classifier.py` |
| 2. Select | Backend list (health-aware + P2C + sticky) | `routing_selector.py`, `router_v3.py`, `sticky_session.py` |
| 3. Inject | Skills, retrieval context, web search, code context | `routing_engine_skills.py`, `skills_injector.py`, `context_pipeline/retrieval_injection.py` |
| 4. Execute | Ordered fallback chain with health recording | `routing_executor.py`, `health_tracker.py` |
| 5. Respond | Format response (OpenAI / Anthropic), attach metadata | `routing_engine_response.py`, `response_builder.py` |

Sub-modules: `routing_engine_context.py` (shared context), `routing_engine_types.py` (`RouteResult` dataclass), `routing_engine_opencode.py` (OpenCode-specific routing).

## Architecture — Backend Registry

`backends_registry.py` defines all providers as a flat `BACKENDS` dict. Each entry:

```python
'provider_name': {
    'url': 'https://api.example.com/v1/chat/completions',
    'key': os.environ.get('PROVIDER_API_KEY', ''),
    'model': 'model-id',
    'fmt': 'openai' | 'anthropic',     # protocol format
    'auth': 'bearer' | 'x-api-key',    # auth header style (default: bearer)
    'timeout': 60,                      # optional, seconds
    'caps': ['tool_calls'],            # optional capabilities
    'force_stream_param': True,        # optional, force stream=true
    'admission': 'code_floor_candidate', # optional, coding pool admission
    'private_code_allowed': True,       # optional
}
```

`backends.py` is a **facade** that re-exports `BACKENDS` from `backends_registry.py` plus detection helpers. `backends_constants.py` holds tier/pool constants.

## Architecture — HTTP Transport Layer

`http_caller.py` is a **thin re-export facade** over:

| Module | Responsibility |
|--------|----------------|
| `http_sync.py` | `call_api()`, `call_raw()`, `probe()` — synchronous httpx calls |
| `http_async.py` | `call_api_async()`, `call_raw_async()` — async httpx calls |
| `http_stream.py` | `call_api_stream()`, `call_api_stream_async()` — SSE streaming |
| `http_request_builder.py` | Client factory, headers, body construction, key pool selection |
| `http_response.py` | Answer extraction, usage parsing, SSE chunk parsing |
| `http_errors.py` | `BackendError`, status code helpers, retry-after extraction |

`router_http.py` is the **legacy urllib path** — prefer `http_caller` for all new code.

## Architecture — OpenCode Module Family

`opencode_*.py` files form a coherent subsystem for OpenCode IDE integration:

| Module | Purpose |
|--------|---------|
| `opencode_config.py` | Config center — constants read at **import time** (env changes need restart) |
| `opencode_error_adapter.py` | Overflow detection (HTTP 413), error response building, retryable classification |
| `opencode_message_normalizer.py` | Message normalization pipeline (incl. Bedrock format) |
| `opencode_tool_schema.py` | Tool schema generation for OpenAI-format tools |
| `opencode_tool_routing.py` | Tool-aware routing decisions |
| `opencode_tool_splitter.py` | Split tool calls from text responses |
| `opencode_tool_repair.py` | Repair malformed tool calls |
| `opencode_reasoning_bridge.py` | reasoning_effort / thinking token passthrough |
| `opencode_sampling.py` | Temperature/top_p sampling adjustments |
| `opencode_truncate.py` | Context truncation for token limits |
| `opencode_prompt_cache.py` | Prompt caching hints |
| `opencode_system_prompt.py` | System prompt construction |
| `opencode_output_limit.py` | Output token limit enforcement |
| `opencode_provider_namespace.py` | Provider-specific namespace handling |
| `opencode_request_headers.py` | Provider-specific request headers |
| `opencode_retry_policy.py` | Retry policy configuration |
| `opencode_schema_sanitize.py` | JSON schema sanitization |
| `opencode_media_detect.py` | Media/image content detection |
| `opencode_overflow_detect.py` | Overflow detection utilities |
| `opencode_compaction_signal.py` | Context compaction signaling |
| `opencode_doom_loop.py` | Doom loop detection for tool calls |
| `opencode_token_bridge.py` | Token counting bridge |

Default tool mode: `LIMA_OPENCODE_TOOL_MODE=direct` (OpenAI-format tools on direct routing path).

## Architecture — Routes Directory

`routes/` (~80 files) is organized by concern. All routers are centrally mounted via `routes/route_registry.py` with `RouteRegistryDeps`; `server.py` wires dependencies with `inject_state()` / `inject_deps()`, not FastAPI `Depends`.

| Group | Key Files | Purpose |
|-------|-----------|---------|
| Chat endpoints | `chat_endpoints.py`, `chat_handler.py`, `chat_stream.py`, `chat_preflight.py` | OpenAI `/v1/chat` and Anthropic `/v1/messages` |
| Anthropic protocol | `anthropic_messages_handler.py`, `anthropic_stream.py` | Native Anthropic message format, SSE streaming |
| Admin | `admin_api.py`, `admin_ui.py`, `admin_state.py` | Backend CRUD, Apple-style HTML UI (`admin.html`) |
| Agent tasks | `agent_tasks.py` + `agent_*.py` submodules | Task dispatch — NOT on chat hot path |
| Tool forwarding | `tool_forward.py`, `tool_forward_stream.py` | OpenCode native tool call forwarding |
| Quality | `quality_gate.py`, `quality_gate_window.py` | Route-level quality retry (≠ root `quality_gate.py` for coding eval) |
| Telegram | `telegram_*.py` | Bot commands, knowledge base, eval tools |
| Device gateway | `device_gateway_*.py` | MQTT + WebSocket device control |
| Ops | `ops_metrics.py`, `request_tracking.py` | Metrics collection, IP/location tracking |
| Stream | `stream_handlers.py`, `opencode_direct_stream.py` | SSE streaming outside routing_engine |
| Registry | `route_registry.py` | Central route mounting via `RouteRegistryDeps` |

## Architecture — Context Pipeline

`context_pipeline/` (~46 files) provides retrieval-augmented context injection. Production uses pieces selectively — `factory.build_default_pipeline()` is a **lab/test harness only**:

| Concern | Key Module | Production? |
|---------|-----------|-------------|
| Retrieval injection | `retrieval_injection.py` | ✅ Used by routing_engine |
| Web search | `web_search.py` | ✅ Search gateway integration |
| Code context | `code_context.py` | ✅ Code-aware context building |
| Context compression | `context_compressor.py` | ✅ Token budget management |
| Auto indexing | `auto_indexer.py` | ✅ Background code indexing (lifespan) |
| Guardrails | `guardrails.py` | Optional preflight |
| Factory pipeline | `factory.py` | 🔬 Lab/test harness only |

## Architecture — Agent Runtime

`agent_runtime/` (~29 files) implements autonomous agent execution — **strictly isolated from the chat hot path**:

| Concern | Key Module |
|---------|-----------|
| Orchestrator | `orchestrator.py` (facade) + `orchestrator_*.py` submodules |
| Task queue | Local lease queue, NOT on chat hot path |
| Permissions | Shell, git, network sandbox permission model |
| Audit | Execution audit trail |

Keep agent execution, permissions, audit, and task queue strictly separated from `routing_engine`.

## Pattern — Dependency Injection

LiMa avoids global mutable state and FastAPI `Depends`. Modules expose `inject_state()` / `inject_deps()` functions that receive their dependencies at import time:

```python
# Module declares what it needs
def inject_deps(*, model_id, record_request, record_fallback, build_pollinations_url):
    global _model_id, _record_request
    _model_id = model_id
    _record_request = record_request
    ...

# server.py wires at import time (NOT via Depends)
_inject_chat_handler_deps(
    model_id=MODEL_ID,
    record_request=_record_request,
    ...
)
```

Rules:
- New shared modules: no global mutable state; expose `inject_state()` / `inject_deps()`.
- Wiring happens in `server.py` at import time, not via FastAPI `Depends`.
- Optional subsystems: `ImportError` → `logger.debug` with description; never silent `except: pass`.

## Module Ownership

| Concern | Authority | Legacy / Avoid | Notes |
|---------|-----------|----------------|-------|
| Backend registry | `backends_registry.py` + `backends_constants.py` | `backends.py` (re-export facade) | Check facade before adding logic |
| Intent + classify | `routing_classifier.py` via `routing_engine` | `smart_router.classify` | |
| Backend select + fallback | `routing_selector.py` + `routing_executor.py` | `router_v3.py` | P2C/sticky in `router_v3` / `sticky_session.py` |
| Health / cooldown | `health_tracker.py` | `router_circuit_breaker.py` | Prefer health_tracker for new code |
| HTTP transport | `http_caller.py` → `http_sync/async/stream` | `router_http.py` (urllib) | Migrate callers to httpx |
| Streaming bridge | `streaming.py`, `routes/stream_handlers.py` | `routes/anthropic_stream.py` | |
| Skills inject | `skills_injector.py` | — | Temperature-gated |
| Semantic cache | `semantic_cache.py` | — | temperature=0 only |
| Session memory | `session_memory/store*.py` | — | Split: db/crud/promote/admin |
| Quality retry (route) | `routes/quality_gate*.py` | — | **Different** from root `quality_gate.py` (coding eval) |
| Agent tasks | `routes/agent_tasks.py` + submodules | — | Not on chat hot path |
| Agent runtime | `agent_runtime/` | — | Isolated from `routing_engine` |
| Budget | `budget_manager.py` | — | Wired from routing_engine |
| Admin panel | `routes/admin_api.py` + `routes/admin_ui.py` | — | Apple-style UI, backend CRUD |
| Telegram | `routes/telegram*.py` | — | Bot commands, knowledge, eval tools |
| Device gateway | `routes/device_gateway*.py` + `device_gateway/` | — | MQTT + WebSocket |
| Tool forwarding | `routes/tool_forward.py` + `routes/tool_forward_stream.py` | — | OpenCode tool call forwarding |

- `smart_router.py` is **legacy utility/compat code** — do not make it the new production authority. It delegates or mirrors `routing_engine`.
- `agent_runtime/` is not on the chat hot path. Keep agent execution, shell/git/network permissions, audit, and task queue isolated from `routing_engine`.

## OpenCode-Specific Gotchas

- OpenCode tuning constants in `opencode_config.py` are read at **import time**; `LIMA_OPENCODE_*` env changes require process restart.
- Default tool mode is `LIMA_OPENCODE_TOOL_MODE=direct`.
- Overflow behavior guarded by `opencode_error_adapter.py`; preserve HTTP 413 and SSE error semantics.
- `.lima-code/settings.json` is the repo-local IDE reference. No root `opencode.json`.
- `opencode-source/` is a gitignored upstream reference clone; do not treat as LiMa source.

## Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LIMA_API_KEY` / `LIMA_API_KEYS` | (required) | Server auth; startup fails if missing |
| `LIMA_OPENCODE_TOOL_MODE` | `direct` | OpenCode tool routing mode |
| `LIMA_IDE_POOL_EVIDENCE_GATE` | `1` | Require eval evidence for IDE default pool |
| `LIMA_ROUTER_HTTP_HTTPX` | `1` | `router_http` delegates to `http_caller` |
| `LIMA_WORKSPACE_READ_GATE` | `0` | Block edit if file not read (sandbox) |
| `LIMA_PERIODIC_CODING_EVAL` | `1` (VPS) | Periodic coding eval on VPS |
| `LIMA_DEBUG` | `0` | Debug mode for http_caller |
| `LIMA_DOCS_ENABLED` | `""` | `1/true/yes` enables Swagger/ReDoc docs endpoints |
| `VPS_HOST` | `47.112.162.80` | VPS address for deploy scripts (replaces hardcoded IP) |
| `SENTRY_DSN` | (empty) | Optional Sentry error tracking |
| `SENTRY_TRACES_RATE` | `0.1` | Sentry trace sampling rate |

New capabilities should default off behind explicit `LIMA_` env flags.

## Server Lifespan

`server_lifespan.py` starts/stops background services via FastAPI lifespan context manager. All imports are optional (`ImportError` → debug log, no crash):

- `backend_admission_store.apply_startup()` — load admission data
- `health_bootstrap.bootstrap_runtime_health()` — seed health state
- `probe_loop.start()` — periodic backend health probing
- `periodic_coding_eval.start()` — scheduled coding eval
- `session_memory.daemon` — SQLite session daemon
- `routes.telegram` — Telegram webhook
- `device_gateway` — device gateway runtime + MQTT
- `observability.structured_logging` — structured log setup
- `context_pipeline.auto_indexer` — auto code indexing

Graceful shutdown (finally block) closes:
- httpx sync/async client pools (`http_request_builder._sync_client_pool`, `_async_client_pool`)
- SQLite connections via `sqlite_manager.close_all()`

## Coding Rules

- Target: files < 300 lines, functions < 50 lines. Prefer extraction over adding to oversized files.
- **No silent degradation**: `except Exception: pass` is forbidden; log at least `logger.warning` with exception type.
- Avoid local imports inside functions unless for optional deps (can cause `UnboundLocalError`).
- Async code: `asyncio.sleep()` or `asyncio.to_thread()`, never `time.sleep()`.
- New shared modules: no global mutable state; expose `inject_state()` / `inject_deps()` for runtime state.
- Keep changes minimal. No backward-compat layers unless persisted data, shipped behavior, or external consumers require it.
- Optional subsystems: `ImportError` → `logger.debug` with description; never silently swallow unknown exceptions.

## Common Pitfalls

- **PowerShell `&&`**: Use `;` or `if ($?) { ... }` — `&&` is not a valid statement separator in PowerShell.
- **Port check**: Avoid `nc`; use `Test-NetConnection` (PowerShell) or `Invoke-RestMethod`.
- **git status line count**: Avoid `wc -l` on Windows; use `Measure-Object` in PowerShell.
- **ruff F401 auto-fix**: Re-export facades (`http_caller.py`, `backends.py`, `smart_router.py`, `routing_engine.py`) have per-file `F401` ignores in `ruff.toml`. Running `ruff check --fix` may incorrectly remove their re-exports.
- **OpenCode config import-time**: Constants in `opencode_config.py` are read at **import time**; `LIMA_OPENCODE_*` env changes require process restart.
- **HTTP 200 empty response**: An HTTP 200 with empty body means the backend is **unavailable** — treat as failure, not success.
- **SearchReplace uniqueness**: The tool requires `original_text` to be a unique, long-enough string in the file. Provide surrounding context to ensure uniqueness.
- **`time.sleep()` in async**: Use `asyncio.sleep()` or `asyncio.to_thread()`; never `time.sleep()` in async code.
- **Silent degradation**: `except Exception: pass` is forbidden; log at least `logger.warning` with exception type.

## Superpowers Principles

1. **Documentation first**: Non-trivial changes need a design doc in `docs/`.
2. **Small focused files**: Single file ≤ 300 lines, function ≤ 50 lines.
3. **Local verify before deploy**: Test locally, then one-shot replace on VPS.
4. **Never break production**: Rollback-ready; new modules in separate files, confirm before wiring to main path.
5. **Reference best practices**: Design decisions backed by open-source reference or real tests.
6. **Progressive replacement**: Old and new run in parallel; small-traffic validation before full cutover.

## Environment And Secrets

- `.env` must define `LIMA_API_KEY` or `LIMA_API_KEYS`; server startup fails if missing.
- Never hardcode provider keys/tokens; use environment variables.
- Do not commit: `.env`, local DBs, `.lima-data/`, `.claude/`, `.qoder/`, `_*.py` debug scripts, generated caches.

## Key Infrastructure Modules

| Module | Purpose |
|--------|--------|
| `sqlite_manager.py` | Unified SQLite connection manager (WAL mode, busy_timeout=30s) |
| `rate_limiter.py` | IP rate limiting with TTL eviction (5 min stale, 60s cleanup) |
| `server.py` | FastAPI app + Sentry init (HttpxIntegration, sensitive header filter) |

## Deployment And Git

- Deploy via `scripts/deploy_unified.py` which uses `systemctl restart lima-router.service`.
- Push to `main` triggers CI → Docker/GHCR deploy to VPS with rollback (`.github/workflows/deploy.yml`).
- Before commit: inspect `git status`, `git diff`, recent log. Stage **only** files related to the change; never `git add .`.
- Working tree may contain unrelated changes. Do not revert, reset, checkout, or modify unrelated files.
- Do not amend commits, force-push, or create PRs unless explicitly requested.

## Documentation Authority

| Document | Purpose |
|----------|---------|
| `AGENTS.md` (this file) | Architecture overview and agent guidance |
| `STATUS.md` | Current milestone state and deployment status |
| `docs/REQUEST_PIPELINE_AUTHORITY.md` | Authoritative request pipeline and module ownership |
| `docs/ROUTING_ENGINE_DESIGN.md` | Routing engine 5-layer design |
| `docs/PRODUCT_DEFINITION.md` | Product scope and boundaries |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | Deploy and release procedures |
| `docs/EXTERNAL_REPOS.md` | Decoupled local clones (deepcode-cli, opencode-source) |
| `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md` | Quality backlog |
| `docs/SMART_ROUTER_MIGRATION.md` | smart_router migration plan and caller list |
| `docs/opencode-integration.md` | OpenCode integration guide |
| `docs/archive/` | Historical plans — do not use for current priorities |

## Project Skills (.qoder/skills/)

This repository ships project-specific Qoder skills. Load via `Skill` tool when relevant:

| Skill | Purpose |
|-------|---------|
| `lima-architecture` | Architecture navigation: request pipeline, module discovery, dependency injection, protocol handling |
| `lima-deploy` | Automated VPS deployment: SSH, backup, upload, restart, `/health` smoke, rollback |
| `lima-fastapi-standards` | Python/FastAPI coding standards: async patterns, error handling, import conventions, anti-patterns |
| `superpowers` | Enforces Superpowers principles: anti-degradation, small files, safe deploy, progressive replacement |
| `ui-ux-pro-max` | UI/UX design intelligence for admin panel (`admin.html`) and web interfaces |
