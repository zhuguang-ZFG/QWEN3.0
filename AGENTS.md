# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

> **M-OC0**: LiMa CLI migrated to OpenCode MCP bridge. `lima-code` → `lima`. See `docs/opencode-integration.md`.
>
> **Authority**: This file is the **authoritative** architecture and convention reference. `CLAUDE.md` is a condensed subset that defers here for full details.

## Project Overview

LiMa is a **multi-model intelligent routing AI coding assistant backend**. It provides an OpenAI-compatible API (`/v1/chat/completions`, `/v1/messages`) that automatically selects the best backend model based on request intent, capability, cost, and quality. This is a **personal coding assistant**, not a commercial platform. Payment, public registration, commercial quota/billing, and customer dashboards are **paused**.

- **Tech stack**: Python 3.10, FastAPI, uvicorn, httpx, SQLite, Redis (optional), pybreaker
- **Runtime**: Port 8080, single-process async, Docker or bare metal
- **Backends**: 180+ cloud AI providers (SCNet, Kimi, MiMo, LongCat, Cloudflare, NVIDIA, OpenRouter, etc.)
- **Dual protocol**: OpenAI (`/v1/chat/completions`) and Anthropic (`/v1/messages`); `converters/anthropic_format.py` handles translation
- **Primary clients**: OpenCode (IDE), Cursor, Claude Code, VS Code Copilot, Telegram

### Repository Scale (2026-06 estimate)

~850 Python files, ~113k lines, ~233 test files, ~71 route files, ~43 top-level directories. Run `python scripts/repo_stats.py` for current numbers.

## Build & Run Commands

> **Windows PowerShell**: This project develops on Windows. Use `;` not `&&` to chain commands.

```bash
# Install dependencies
pip install -r requirements_server.txt

# Start server (local)
python server.py
# or: python -m uvicorn server:app --host 0.0.0.0 --port 8080

# Docker (docker-compose.yml includes lima + searxng sidecar)
docker compose build
docker compose up -d

# Makefile shortcuts
make test          # pytest + ruff check
make lint          # ruff check + ruff format --check
make format        # ruff format .
make deploy        # python scripts/deploy_unified.py
make smoke-test    # curl /health + /v1/models
make docker-build  # docker compose build
```

### Testing

```bash
# Full test suite (pytest, test dir = tests/)
pytest --tb=short -q

# Full suite excluding CI gates
python -m pytest tests/ -q --ignore=tests/test_ci_gates.py

# Single test file
pytest tests/test_routing_engine.py -v

# Single test by name
pytest tests/test_http_caller_concurrency.py::test_concurrent_calls -v

# Property-based tests (Hypothesis)
pytest tests/test_hypothesis_routing.py -v

# Skip offline RAG eval fixtures
pytest -m "not rag_gate"

# Using project venv explicitly (Windows)
.venv310\Scripts\python.exe -m pytest tests/ -q --tb=short
```

`pytest.ini` sets `asyncio_mode = auto`, `testpaths = tests`, `pythonpath = .`. Custom marker: `rag_gate` for offline RAG eval fixtures.

### Linting & Type Checking

```bash
# Lint (ruff, config in ruff.toml — targets py310, line-length 120)
ruff check .

# Format check / auto-format
ruff format --check
ruff format .

# Type checking (pyright, config in pyrightconfig.json — basic mode)
# Only checks: routes/, context_pipeline/, agent_runtime/, session_memory/,
#   lima_mcp/, tool_gateway/, and select top-level files (server.py, routing_engine.py, etc.)
pyright

# Repo stats
python scripts/repo_stats.py
```

Ruff selects: `E9, F821, F822, F823, B005, B011, B012, B905, S507`. Per-file F401 ignores exist for facade re-export files (`http_caller.py`, `smart_router.py`, `backends.py`, `routing_engine.py`, `**/__init__.py`).

Ruff excludes non-core dirs (`deepcode-cli`, `esp32S_XYZ`, `venv`, `scripts/archive`, etc. — see `ruff.toml` for full list).

### CI Pipeline (GitHub Actions)

`.github/workflows/test.yml` runs on push/PR to `main`:
1. Ruff lint (`ruff check .`)
2. **Bandit security scan** (`bandit -r agent_runtime/ routes/ -ll`) — catches security issues in agent runtime and routes
3. Pytest (`pytest --tb=short -q`)

`.github/workflows/deploy.yml` auto-deploys to VPS on push to `main` (after tests pass). Includes automatic rollback on health check failure and Telegram notification.

### Root-Level Test Files

Several `test_*.py` files live at the project root **in addition to** `tests/`. These are older or integration-focused tests. The canonical test directory is `tests/` (set in `pytest.ini`). Root-level tests are not included in default `pytest` runs.

### Smoke Test

```bash
curl -sf http://127.0.0.1:8080/health && echo " OK"
curl -sf http://127.0.0.1:8080/v1/models | python -m json.tool
```

## Architecture

### Request Pipeline

```
Client (OpenCode/Cursor/VS Code/Telegram)
  → server.py (FastAPI app + BodySizeLimitMiddleware, 32MB limit)
  → routes/chat_endpoints.py (OpenAI/Anthropic protocol dispatch + auth)
  → routes/chat_preflight.py (validation)
  → opencode_message_normalizer.py (surrogate cleanup, toolCallId adapt)
  → opencode_error_adapter.py (overflow detection, 18+ regex patterns → HTTP 413)
  → routing_engine.route()
      ├─ identity_guard       (self-identification detection)
      ├─ semantic_cache       (temperature=0 deterministic cache)
      ├─ routing_classifier   (classify intent + scenario)
      ├─ context_pipeline     (retrieval, web search, code context, enrich)
      ├─ skills_injector      (backend-aware skill injection)
      ├─ code_orchestrator    (coding scenario handling)
      ├─ routing_selector     (backend selection: health, sticky, budget)
      ├─ routing_executor     (execute with fallback chain)
      ├─ speculative          (parallel speculative calls for simple queries)
      └─ response_validator   (coding answer quality check + retry)
  → http_caller → http_sync / http_async / http_stream (HTTP transport)
  → route_post_process.py + response_cleaner.py (post-process)
  → routes/chat_post_closeout.py (memory, observability, distill)
  → Usage tracking (x-lima-usage header) + reasoning_effort parameter passthrough
```

### Server Startup & Dependency Injection

`server.py` is the FastAPI entry point. It does **not** use FastAPI's `Depends`. Instead, it uses explicit DI:

1. `server_bootstrap.create_runtime_state()` creates the stats dict, locks, and backend maps.
2. `server.py` calls `inject_state()` / `inject_deps()` on each module to wire dependencies.
3. `routes/route_registry.py` uses a `RouteRegistryDeps` dataclass to bundle all injected dependencies and calls `register_all_routes(app, deps)` which mounts every FastAPI router.
4. `server_lifespan.py` manages async lifespan — each subsystem starts/stops sequentially and is optional (guarded by `ImportError` with `_log.debug`).

**Startup order** (lifespan — all optional subsystems guarded by `ImportError` + `_log.debug`):
`backend_admission_store` → `probe_loop` (always starts) → `periodic_coding_eval` → `session_memory.daemon` → Telegram webhook → Device gateway → Structured logging → SSE event loop → MQTT client → `context_pipeline.auto_indexer`

`route_registry.py` also tracks which optional modules loaded via `deps.loaded_modules` dict (used by `/health` and admin endpoints).

**Rule for new modules**: Avoid global mutable state. Expose `inject_state()` / `inject_deps()` functions. State is created at startup and injected.

### Facade Pattern

Several top-level modules are **thin re-export facades** — they contain no logic, only `from X import Y` statements. Always check if a module is a facade before adding logic to it:

| Facade | Re-exports from |
|--------|----------------|
| `backends.py` | `backends_registry.py` + `backends_constants.py` + detection helpers; also contains enable/disable state management, capability queries, and startup check |
| `http_caller.py` | `http_sync`, `http_async`, `http_stream`, `http_request_builder`, `http_response`, `http_errors` |
| `smart_router.py` | Legacy utility module — provides `analyze()`, `detect_image_intent()`, `detect_thinking_intent()`, circuit breaker, and ROUTE table to production pipeline. Also loads local Qwen3 router model. NOT a routing_engine delegate. |

> **Note**: `routing_engine.py` re-exports some sub-module symbols but is **NOT** a facade — it contains the full `route()` orchestration function (classify → enrich → inject → select → execute → validate → respond). Do not treat it as a thin re-export module.

### Backend Configuration

- `backends_registry.py`: Dict of 180+ backend configs (name → `{url, model, key, caps}`)
- `backends_constants.py`: Capability lists (`CODE_CAPABLE_BACKENDS`, `VISION_BACKENDS`, `THINKING_BACKENDS`, `WEAK_BACKENDS`, `GFW_BACKENDS`, etc.)
- `backends.py`: Facade combining both, plus `detect_vendor()`, `detect_tier()`, `detect_caps()`, `backend_has_capability()`, `is_enabled()`, `get_configured()`
- `health_tracker.py`: Health state tracking — prefer over `router_circuit_breaker.py` for new code
- `model_resolver.py`: Maps client `model` param to specific backend; supports override

### Protocol Handling

| Protocol | Entry Point | Tool Format | Streaming |
|----------|-------------|-------------|-----------|
| OpenAI | `/v1/chat/completions` | `tool_calls[]` in message | SSE `data: {...}` |
| Anthropic | `/v1/messages` | `tool_use` content block | SSE `event: ...` |

Key converter: `converters/anthropic_format.py` handles Anthropic↔OpenAI format translation including `tool_choice` passthrough.

Tool call pipeline:
- **Tier1** = OpenAI native `tool_calls` passthrough (GPT-4o, GitHub Models)
- **Tier2** = Anthropic-native tools forwarded to capable backends
- **OpenCode direct mode** (`LIMA_OPENCODE_TOOL_MODE=direct`, default): bypasses Anthropic conversion, handles tools natively in OpenAI format via `routing_engine`

### Key Subsystems

| Subsystem | Entry Module | Structure |
|-----------|-------------|-----------|
| **Route registration** | `routes/route_registry.py` | Central `register_all_routes()` mounts all routers; uses `RouteRegistryDeps` dataclass |
| **Routing decision** | `routing_engine.py` | classify → enrich → inject → select → execute → validate → respond |
| **HTTP transport** | `http_caller.py` (facade) | `http_sync`, `http_async`, `http_stream`, `http_request_builder`, `http_response`, `http_errors` |
| **Streaming** | `streaming.py` | Tool-native vs simulated SSE; `routes/stream_handlers.py` |
| **OpenCode config** | `opencode_config.py` | All OpenCode-specific tuning knobs (tool mode, rate limit, fast boost, preferred backend, compression). Values read at import time. |
| **OpenCode overflow** | `opencode_error_adapter.py` | 18+ regex patterns for context overflow → HTTP 413 + SSE error event |
| **OpenCode messages** | `opencode_message_normalizer.py` | Surrogate cleanup, toolCallId adapt, content part filter |
| **Context pipeline** | `context_pipeline/` (45 files) | Retrieval injection, web search, code context, enrichment, compression, auto-indexer, skill store, response validation, semantic code retrieval, token budget, reranking |
| **Session memory** | `session_memory/` (18 files) | Split: `store_db` (schema), `store_crud` (operations), `store_promote` (promotion), `store_admin` (admin ops); also `daemon.py`, `compactor.py`, `learning_loop.py`, `prompt_recall.py`, `shadow_mode.py` |
| **Agent runtime** | `agent_runtime/` (29 files) | `orchestrator.py` (facade) → `orchestrator_queue.py` + `orchestrator_worker.py`; also `executor.py`, `approval.py`, `tool_exec.py`, `shell_executor.py`, `git_executor.py`, `network_executor.py` |
| **Telegram bot** | `routes/telegram*.py` (17 files) | Commands, dispatch, knowledge, dev skills, eval tools, CI tools, diag tools |
| **Device gateway** | `device_gateway/` (17 files) | ESP32/hardware WebSocket + MQTT; `protocol.py`, `path_pipeline.py`, `redis_store.py`, `mqtt_client.py` |
| **Channel gateway** | `channel_gateway/` (20 files) | Multi-channel (Telegram, web) message routing; `service.py`, `store.py`, `branding.py`, `commands.py` |
| **Reverse gateway** | `reverse_gateway/` (14 files) | Adapters for reverse-engineered free AI platforms; `providers/scnet.py` is the primary adapter |
| **Search gateway** | `search_gateway/` (15 files) | Web search integration: SearXNG meta-search, Gitee OpenAPI search |
| **Quality gate** | `routes/quality_gate*.py` | Coding eval retry; split into tiers/direct sub-modules |
| **Tool forwarding** | `routes/tool_forward*.py` | Sync + streaming tool call forwarding to capable backends (Tier1/Tier2) |
| **Admin panel** | `routes/admin*.py` (~10 files) | Dashboard, backends CRUD, client keys, auth, UI |
| **MCP server** | `lima_mcp/` | Model Context Protocol integration |
| **Observability** | `observability/` | Structured logging, metrics |
| **Usage tracking** | `routes/chat_post_closeout.py` | x-lima-usage header injection |

### External repos & local clones (not tracked)

- `deepcode-cli/` — LiMa CLI (separate repo, **decoupled** 2026-06-05). Maintenance mode; clone locally if needed — see `docs/EXTERNAL_REPOS.md`. Config dir `.lima/` is still the OpenCode settings reference in this repo.
- `esp32S_XYZ/` — ESP32 firmware (separate repo, **decoupled**). Optional hardware work — clone outside or under ignored path.
- `opencode-source/` — OpenCode upstream reference clone (gitignored). Used for `reasoning_variants` / error adapter parity.
- `_codegraph_repo/` — CodeGraph tool (separate git repo, not part of LiMa core)
- `infra/` — Proxy scripts for reverse-engineered backends (Kimi, SCNet)
- `deploy/` — Deployment configs for sidecar services

### Venv & Python Path

Project venv is at `.venv310/`. Use `.venv310\Scripts\python.exe` on Windows to run tests or scripts explicitly. `pyrightconfig.json` targets Python 3.10 with `basic` type checking mode.

## Environment Variables

Copy `.env.example` to `.env`. Critical vars:
- `LIMA_API_KEY` / `LIMA_API_KEYS` — **required** at startup; server errors if missing
- `LIMA_ADMIN_TOKEN` — admin panel auth
- `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_TOKEN` — nuclear fallback backend (last resort, direct Cloudflare call bypassing all routing)
- Provider API keys: `CLAUDE_API_KEY`, `DEEPSEEK_API_KEY`, `NVIDIA_API_KEY`, etc.
- Feature flags: `GITEE_WEBHOOK_ENABLED`, `GITHUB_WEBHOOK_ENABLED`, `SEARXNG_ENABLED`, etc. (default off)
- `LIMA_DEVICE_TOKENS` — device gateway per-device auth
- `LIMA_OPENCODE_TOOL_MODE` — `direct` (default) or `convert` for tool call handling
- `LIMA_OPENCODE_*` — 6 additional OpenCode tuning vars (fast boost, rate multiplier, preferred backend, context turns, speculative tools, model list); see `opencode_config.py` and `.env.example`
- `SENTRY_DSN` — optional error tracking

### OpenCode IDE Config

`.lima-code/settings.json` holds IDE-specific config (BASE_URL, MODEL, MCP servers). This is the local OpenCode configuration directory.

## Superpowers Hard Rules

### 0. No Silent Degradation

All features must work under correct config. No silent fallbacks.

- `.env` must set `LIMA_API_KEY` / `LIMA_API_KEYS`; server must error on missing, not degrade
- `except Exception: pass` or `except ImportError: pass` on production paths is **forbidden** — must at least `logger.warning` with reason
- If critical deps (chromadb, tree-sitter) are missing, log explicit warning at startup, not silent runtime degradation
- All feature gates use explicit env flags; new capabilities default off

### 0.1 Real-Environment Verification

- VPS deployments must be verified on VPS, not just localhost
- Public API must be tested with real tokens via public domain
- Telegram commands must be tested via real Telegram messages
- Never mark verification as "skipped" or "pending" — diagnose and fix

### 0.2 .env Deployment Protection

- Backup VPS `.env` before any deployment
- Use `cat >> .env` to append new vars, never overwrite
- Verify critical services (Telegram webhook, API key auth) immediately after deploy

## Code Quality Rules

- **File size**: Target ≤300 lines per file, ≤50 lines per function. Exceeding: split into files, not wrap in comments.
- **No bare excepts**: `except Exception: pass` is forbidden; at minimum `logger.warning` + exception type
- **No hardcoded secrets**: Never hardcode API keys/tokens in production paths; read from `.env` via `os.environ`
- **New modules**: Must be independent files first, integrate into core path only after verification
- **Facade pattern**: Check before adding logic — several top-level modules are thin re-export facades
- **Import convention**: Module-level imports preferred. Local `from X import Y` inside functions risks `UnboundLocalError` shadowing the name for the entire function scope.
- **Async safety**: Never use `time.sleep()` in async code; use `asyncio.sleep()` or `asyncio.to_thread()`
- **Naming**: `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, `LIMA_` prefix for env vars, leading `_` for private functions
- **DI pattern**: New modules expose `inject_state()` / `inject_deps()` — no global mutable state
- **Logging**: `logger = logging.getLogger(__name__)`; use `info` for milestones, `warning` for degradation, `error` with `exc_info=True` for unexpected failures
- **Type hints**: Preferred for function signatures; use py310 syntax (`list[dict]`, not `List[Dict]`). Pyright is `basic` mode — aim for clarity, not full coverage

### Import Convention Pitfall

```python
# BAD: local import shadows module-level name for entire function
def handler():
    from chat_request_utils import extract_last_user_text  # SHADOWS!
    # Python treats extract_last_user_text as local for entire function
    # Even code paths that don't reach this line get UnboundLocalError

# GOOD: import at module level
from chat_request_utils import extract_last_user_text
```

## Deployment

### VPS Deployment Flow

1. Local pytest (focused for the change; full suite for production code changes)
2. `ruff check` + `pyright` if production code changed
3. Backup current VPS version
4. Deploy via `scripts/deploy_*.py` or `scripts/deploy_unified.py`
5. Restart + `/health` + public HTTPS smoke + slice-specific smoke
6. Update `progress.md` / `findings.md` with evidence
7. `git add` (only milestone-related files) → `git commit` → `git push origin` → `git push gitee`

See `docs/DEPLOY_AND_RELEASE_CONVENTION.md` for the authoritative 8-step closeout protocol.

### Common Deploy Scripts

| Slice | Deploy Script | Smoke Script |
|-------|--------------|-------------|
| Unified | `scripts/deploy_unified.py` | `/health` + manual |
| Admin panel | `scripts/deploy_m22_m26_admin.py` | Admin panel smoke |
| VPS bundle | `scripts/deploy_vps_bundle.py` | Full service smoke |

### Docker

```bash
docker compose build
docker compose up -d
docker compose down
```

Docker health check: `curl -f http://localhost:8080/health`. Multi-stage build (`Dockerfile`): builder installs deps, runtime copies only `/install`.

## Git Conventions

- **Never** `git add .` — only stage milestone-related files
- **Never** commit `.env`, tokens, VPS passwords, `.lima-data/`, generated caches, reference repos
- **Never** stage `.claude/`, `.qoder/`, temp debug scripts (`_*.py`), or credentials
- Use conventional commits (e.g., `feat:`, `fix:`, `refactor:`)
- Push to both GitHub (`origin`) and Gitee mirror (`gitee`)
- Working tree may contain unrelated user changes — do not `git reset` or `git checkout`
- No git submodules in this repo (as of 2026-06-05). External clones: `docs/EXTERNAL_REPOS.md`. `_codegraph_repo` is a separate local git repo if present, not a submodule.

## Key Entry File Sizes

| File | Lines | Notes |
|------|------:|-------|
| `server.py` | 146 | FastAPI entry + `BodySizeLimitMiddleware` |
| `routing_engine.py` | 354 | Core routing orchestration (NOT a facade) |
| `smart_router.py` | 228 | Legacy utility set (analyze/detect), not on main request path |
| `server_lifespan.py` | 106 | Async lifespan startup/shutdown |
| `routes/route_registry.py` | 242 | Central router mounting + `RouteRegistryDeps` |
| `routes/chat_handler_dispatch.py` | 356 | Non-streaming dispatch (**over 300-line target, needs split**) |
| `http_body_limit.py` | 249 | ASGI body size limit middleware |

## Key Documents

| Document | Purpose |
|----------|---------|
| `STATUS.md` | Current project state and milestone history |
| `docs/REQUEST_PIPELINE_AUTHORITY.md` | Authoritative request pipeline module ownership |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | Authoritative deploy + closeout protocol (8 steps) |
| `docs/LIMA_MEMORY.md` | Long-term project memory |
| `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` | Current roadmap |
| `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md` | Code quality backlog |
| `findings.md` | Factual discoveries and ops conclusions |
| `progress.md` | Execution progress log |
| `task_plan.md` | Current task plan with evidence |

## Milestone Collaboration Protocol

1. Owner implements milestone slice
2. Agent reviews code before next milestone starts
3. Agent fixes small review findings
4. Agent runs focused tests → full test suite → `git diff --check`
5. Agent updates `progress.md` / `findings.md` with closeout evidence
6. Agent stages only milestone-related files → commit → push (GitHub + Gitee)
7. Agent proposes next milestone plan only after push

**Auto-closeout** (when user hasn't forbidden it): local pytest → VPS deploy + restart + health/smoke → update docs → git add/commit/push.

Hard rules:
- No "deployed" claim without VPS smoke evidence
- New capabilities default off (env flag); never enable unreviewed flags on VPS
- Deployment failure → record rollback position, never force-push
