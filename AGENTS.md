# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Project Overview

LiMa (力码) is a **multi-model intelligent routing AI coding assistant backend**. It provides an OpenAI-compatible API (`/v1/chat/completions`, `/v1/messages`) that automatically selects the best backend model based on request intent, capability, cost, and quality. Clients include Cursor, Claude Code, VS Code Copilot, Telegram, and a custom CLI (LiMa Code / `deepcode-cli`).

- **Tech stack**: Python 3.10, FastAPI, uvicorn, httpx, SQLite, Redis (optional), pybreaker
- **Runtime**: Port 8080, single-process async, Docker or bare metal
- **Backends**: 180+ cloud AI providers (SCNet, Kimi, MiMo, LongCat, Cloudflare, NVIDIA, OpenRouter, etc.)
- **Dual protocol**: OpenAI (`/v1/chat/completions`) and Anthropic (`/v1/messages`) formats; `converters/anthropic_format.py` handles translation
- **Not a commercial platform** — personal coding assistant; payment/registration/billing are paused

## Build & Run Commands

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

# Single test file
pytest tests/test_routing_engine.py -v

# Single test by name
pytest tests/test_http_caller_concurrency.py::test_concurrent_calls -v

# Property-based tests (Hypothesis)
pytest tests/test_hypothesis_routing.py -v

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
pyright

# Repo stats
python scripts/repo_stats.py
```

Ruff selects: `E9, F821, F822, F823, B005, B011, B012, B905, S507`. Per-file F401 ignores exist for facade re-export files (`http_caller.py`, `smart_router.py`, `backends.py`, `routing_engine.py`, `**/__init__.py`).

Ruff excludes: `codegraph`, `deepcode-cli`, `esp32S_XYZ`, `venv`, `.venv`, `scripts/archive`, and other non-core dirs.

### Smoke Test

```bash
curl -sf http://127.0.0.1:8080/health && echo " OK"
curl -sf http://127.0.0.1:8080/v1/models | python -m json.tool
```

### LiMa Code CLI (deepcode-cli/)

The CLI is a Node.js (≥22) TypeScript/React/Ink terminal app. It is **not published to npm** — install from GitHub.

```bash
cd deepcode-cli
npm install
npm run build        # typecheck + lint + format check + esbuild bundle
npm run bundle       # esbuild only (fast)
npm run test         # node src/tests/run-tests.mjs
npm run lint         # eslint src/
npm run typecheck    # tsc --noEmit
```

Binary entry: `dist/cli.js` (bin name: `lima-code`).

## Architecture

### Request Pipeline (Chat)

```
Client → server.py (FastAPI + BodySizeLimitMiddleware, 32MB limit)
       → routes/chat_endpoints.py (OpenAI/Anthropic protocol dispatch)
       → routes/chat_preflight.py (auth via LIMA_API_KEY, validation)
       → routing_engine.route()          ← authoritative routing entry
           ├─ identity_guard             (self-identification detection)
           ├─ semantic_cache             (temperature=0 deterministic cache)
           ├─ routing_classifier         (classify intent + scenario)
           ├─ context_pipeline           (retrieval, web search, code context, enrich)
           ├─ skills_injector            (backend-aware skill injection)
           ├─ code_orchestrator          (coding scenario handling)
           ├─ routing_selector           (backend selection: health, sticky, budget)
           ├─ routing_executor           (execute with fallback chain)
           ├─ speculative                (parallel speculative calls for simple queries)
           └─ response_validator         (coding answer quality check + retry)
       → http_caller → http_sync/http_async/http_stream (HTTP transport)
       → route_post_process.py + response_cleaner.py (post-process)
       → routes/chat_post_closeout.py (memory, observability, distill)
```

### Key Module Map

| Concern | Authoritative Module | Notes |
|---------|---------------------|-------|
| FastAPI entry | `server.py` | Wires deps via `server_bootstrap.py` + `server_lifespan.py` |
| Route registration | `routes/route_registry.py` | Central `register_all_routes()` mounts all routers; uses `RouteRegistryDeps` dataclass |
| Routing decision | `routing_engine.py` | 5-layer: classify → select → inject → execute → respond |
| Backend registry | `backends_registry.py` + `backends_constants.py` | `backends.py` is a facade re-exporting both |
| HTTP transport | `http_caller.py` | Thin facade over `http_sync`, `http_async`, `http_stream`, `http_request_builder`, `http_response`, `http_errors` |
| Streaming | `streaming.py`, `routes/stream_handlers.py` | Tool-native vs simulated SSE |
| Legacy router | `smart_router.py` | V3 compat layer; delegates to `routing_engine` for production |
| Health tracking | `health_tracker.py` | Prefer over `router_circuit_breaker.py` for new code |
| Session memory | `session_memory/store*.py` | Split: db/crud/promote/admin |
| Agent runtime | `agent_runtime/orchestrator*.py` | Task queue + worker; facade at `orchestrator.py` |
| Context pipeline | `context_pipeline/` | Retrieval injection, web search, code context, enrich, compression, auto-indexer, skill_store |
| Telegram bot | `routes/telegram*.py` | Commands, dispatch, knowledge, dev skills, eval tools |
| Device gateway | `device_gateway/` + `routes/device_gateway*.py` | ESP32/hardware WebSocket + MQTT |
| Admin panel | `routes/admin*.py` | Dashboard, backends CRUD, auth, UI |
| Quality gate | `routes/quality_gate*.py` | Coding eval retry; split into tiers/direct |
| Tool forwarding | `routes/tool_forward*.py` | Forwards tool calls to capable backends |
| Channel gateway | `channel_gateway/` | Multi-channel (Telegram, web) message routing |
| Reverse gateway | `reverse_gateway/` | Adapters for reverse-engineered free AI platforms (providers/ subdir) |
| MCP server | `lima_mcp/` | Model Context Protocol integration |
| Observability | `observability/` | Structured logging, metrics |
| Model resolver | `model_resolver.py` | Maps client `model` param to specific backend; supports override |

### Server Startup

`server_lifespan.py` manages async lifespan. On startup it sequentially attempts to start:
1. `backend_admission_store` — backend admission control
2. `probe_loop` — health probe for all backends (always starts)
3. `periodic_coding_eval` — scheduled coding quality evals
4. `session_memory.daemon` — session memory background worker
5. Telegram webhook
6. Device gateway runtime
7. Structured logging (observability)
8. SSE event loop for admin panel
9. MQTT client (device gateway)
10. `context_pipeline.auto_indexer` — code auto-indexing

Each subsystem is optional (guarded by `ImportError` with `_log.debug`).

### Dependency Injection Pattern

`server.py` uses explicit DI — **not** FastAPI's `Depends`. Modules expose `inject_state()` / `inject_deps()` functions. State (stats dict, locks, backend maps) is created in `server_bootstrap.create_runtime_state()` and injected at startup. `routes/route_registry.py` uses a `RouteRegistryDeps` dataclass to bundle all injected dependencies.

**Rule**: Avoid global mutable state in new modules. Use the `inject_*` pattern.

### Backend Configuration

Backends are defined in `backends_registry.py` (dict of name → config with URL, model, key env var). `backends_constants.py` holds capability lists (`CODE_CAPABLE_BACKENDS`, `VISION_BACKENDS`, `THINKING_BACKENDS`, etc.). Detection helpers (`detect_vendor`, `detect_tier`, `detect_caps`) live in `backends.py` facade.

### Facade Pattern

Several top-level modules are **thin re-export facades** — they contain no logic, only `from X import Y` statements:
- `backends.py` → re-exports from `backends_registry.py` + `backends_constants.py`
- `http_caller.py` → re-exports from `http_sync`, `http_async`, `http_stream`, etc.
- `smart_router.py` → V3 compat shim delegating to `routing_engine`
- `routing_engine.py` → re-exports `classify`, `select`, `execute` from sub-modules

Always check if a module is a facade before adding logic to it.

### Submodules & Sub-projects

- `deepcode-cli/` — LiMa Code CLI (Node.js/TypeScript), git submodule
- `_codegraph_repo/` — CodeGraph tool (separate repo, not part of LiMa core)
- `infra/` — Proxy scripts for reverse-engineered backends (Kimi, SCNet)
- `deploy/` — Deployment configs for sidecar services

## Environment Variables

Copy `.env.example` to `.env`. Critical vars:
- `LIMA_API_KEY` / `LIMA_API_KEYS` — **required** at startup; server errors if missing
- `LIMA_ADMIN_TOKEN` — admin panel auth
- `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_TOKEN` — nuclear fallback backend (last resort)
- Provider API keys: `CLAUDE_API_KEY`, `DEEPSEEK_API_KEY`, `NVIDIA_API_KEY`, etc.
- Feature flags: `GITEE_WEBHOOK_ENABLED`, `GITHUB_WEBHOOK_ENABLED`, `SEARXNG_ENABLED`, etc. (default off)
- `LIMA_DEVICE_TOKENS` — device gateway per-device auth
- `SENTRY_DSN` — optional error tracking

## Superpowers Hard Rules

### 0. No Silent Degradation

All features must work under correct config. No silent fallbacks.

- `.env` must set `LIMA_API_KEY` / `LIMA_API_KEYS`; server must error on missing, not degrade
- `except Exception: pass` or `except ImportError: pass` on production paths is **forbidden** — must at least `logger.warning` with reason
- If critical deps (chromadb, tree-sitter) are missing, log explicit warning at startup, not silent runtime degradation

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

- **File size**: Target ≤300 lines per file, ≤50 lines per function
- **No bare excepts**: `except Exception: pass` is forbidden; at minimum `logger.warning` + exception type
- **No hardcoded secrets**: Never hardcode API keys/tokens in production paths
- **New modules**: Must be independent files first, integrate into core path only after verification
- **Facade pattern**: Several modules (`backends.py`, `http_caller.py`, `smart_router.py`) are thin re-export facades — check before adding logic
- **Import convention**: Module-level imports preferred; local `from X import Y` inside functions risks `UnboundLocalError` shadowing
- **Async safety**: Never use `time.sleep()` in async code; use `asyncio.sleep()` or `asyncio.to_thread()`
- **Naming**: `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, `LIMA_` prefix for env vars

## Deployment

### VPS Deployment Flow

1. Local pytest (focused for the change)
2. `ruff check` + `pyright` if production code changed
3. Backup current VPS version
4. Deploy via `scripts/deploy_*.py` or `scripts/deploy_unified.py`
5. Restart + `/health` + public HTTPS smoke + slice-specific smoke
6. Update `progress.md` / `findings.md` with evidence
7. `git add` (only milestone-related files) → `git commit` → `git push origin` → `git push gitee`

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
- **Never** stage `.claude/`, `.qoder/`, temp debug scripts, or credentials
- Use conventional commits (e.g., `feat:`, `fix:`, `refactor:`)
- Push to both GitHub (`origin`) and Gitee mirror (`gitee`)
- Working tree may contain unrelated user changes — do not `git reset` or `git checkout`
- `.gitmodules` tracks `deepcode-cli` and `_codegraph_repo` submodules

## Key Documents

| Document | Purpose |
|----------|---------|
| `STATUS.md` | Current project state and milestone history |
| `docs/REQUEST_PIPELINE_AUTHORITY.md` | Authoritative request pipeline module ownership |
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
