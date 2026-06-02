# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Project Overview

LiMa (力码) is a **multi-model intelligent routing AI coding assistant backend**. It provides an OpenAI-compatible API (`/v1/chat/completions`, `/v1/messages`) that automatically selects the best backend model based on request intent, capability, cost, and quality. Clients include Cursor, Claude Code, VS Code Copilot, Telegram, and a custom CLI (LiMa Code / `deepcode-cli`).

- **Tech stack**: Python 3.10, FastAPI, uvicorn, httpx, SQLite, Redis (optional), pybreaker
- **Runtime**: Port 8080, single-process async, Docker or bare metal
- **Backends**: 180+ cloud AI providers (SCNet, Kimi, MiMo, LongCat, Cloudflare, NVIDIA, OpenRouter, etc.)
- **Not a commercial platform** — personal coding assistant; payment/registration/billing are paused

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements_server.txt

# Start server (local)
python server.py
# or: python -m uvicorn server:app --host 0.0.0.0 --port 8080

# Docker
docker compose build
docker compose up -d
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
```

`pytest.ini` sets `asyncio_mode = auto`, `testpaths = tests`, `pythonpath = .`.

### Linting & Type Checking

```bash
# Lint (ruff, config in ruff.toml — targets py310, line-length 120)
ruff check .

# Format check
ruff format --check

# Auto-format
ruff format .

# Type checking (pyright, config in pyrightconfig.json — basic mode)
pyright

# Repo stats
python scripts/repo_stats.py
```

Ruff currently selects: `E9, F821, F822, F823, B005, B011, B012, B905, S507`. Per-file ignores exist for facade re-export files (`http_caller.py`, `smart_router.py`, `backends.py`, `routing_engine.py`).

### Smoke Test

```bash
curl -sf http://127.0.0.1:8080/health && echo " OK"
curl -sf http://127.0.0.1:8080/v1/models | python -m json.tool
```

## Architecture

### Request Pipeline (Chat)

```
Client → server.py (FastAPI + BodySizeLimitMiddleware)
       → routes/chat_endpoints.py (OpenAI/Anthropic protocol)
       → routes/chat_preflight.py (auth, validation)
       → routing_engine.route()          ← authoritative routing entry
           ├─ identity_guard             (self-identification detection)
           ├─ semantic_cache             (temperature=0 cache)
           ├─ routing_classifier         (classify intent + scenario)
           ├─ context_pipeline           (retrieval, web search, code context, enrich)
           ├─ skills_injector            (backend-aware skill injection)
           ├─ code_orchestrator          (coding scenario handling)
           ├─ routing_selector           (backend selection: health, sticky, budget)
           ├─ routing_executor           (execute with fallback chain)
           └─ speculative                (parallel speculative calls for simple queries)
       → http_caller → http_sync/http_async/http_stream (HTTP transport)
       → route_post_process.py + response_cleaner.py (post-process)
       → routes/chat_post_closeout.py (memory, observability, distill)
```

### Key Module Map

| Concern | Authoritative Module | Notes |
|---------|---------------------|-------|
| FastAPI entry | `server.py` | Wires deps via `server_bootstrap.py` + `server_lifespan.py` |
| Route registration | `routes/route_registry.py` | Central `register_all_routes()` mounts all routers |
| Routing decision | `routing_engine.py` | 5-layer: classify → select → inject → execute → respond |
| Backend registry | `backends_registry.py` + `backends_constants.py` | `backends.py` is a facade re-exporting both |
| HTTP transport | `http_caller.py` | Thin facade over `http_sync`, `http_async`, `http_stream`, `http_request_builder`, `http_response`, `http_errors` |
| Streaming | `streaming.py`, `routes/stream_handlers.py` | Tool-native vs simulated SSE |
| Legacy router | `smart_router.py` | V3 compat layer; delegates to `routing_engine` for production |
| Health tracking | `health_tracker.py` | Prefer over `router_circuit_breaker.py` for new code |
| Session memory | `session_memory/store*.py` | Split: db/crud/promote/admin |
| Agent runtime | `agent_runtime/orchestrator*.py` | Task queue + worker; facade at `orchestrator.py` |
| Context pipeline | `context_pipeline/` | Retrieval injection, web search, code context, enrich, compression |
| Telegram bot | `routes/telegram*.py` | Commands, dispatch, knowledge, dev skills, eval tools |
| Device gateway | `device_gateway/` + `routes/device_gateway*.py` | ESP32/hardware WebSocket + MQTT |
| Admin panel | `routes/admin*.py` | Dashboard, backends CRUD, auth, UI |
| Quality gate | `routes/quality_gate*.py` | Coding eval retry; split into tiers/direct |
| Tool forwarding | `routes/tool_forward*.py` | Forwards tool calls to capable backends |
| Channel gateway | `channel_gateway/` | Multi-channel (Telegram, web) message routing |
| Reverse gateway | `reverse_gateway/` | Adapters for reverse-engineered free AI platforms |
| MCP server | `lima_mcp/` | Model Context Protocol integration |
| Observability | `observability/` | Structured logging, metrics |

### Server Startup

`server_lifespan.py` manages async lifespan: starts probe loop, periodic coding eval, session memory daemon, Telegram webhook, device gateway runtime, MQTT client, and auto-indexer. Each subsystem is optional (guarded by `ImportError`).

### Dependency Injection Pattern

`server.py` uses explicit DI: modules expose `inject_state()` / `inject_deps()` functions. State (stats dict, locks, backend maps) is created in `server_bootstrap.create_runtime_state()` and injected into route modules at startup. Avoid global mutable state in new modules.

### Backend Configuration

Backends are defined in `backends_registry.py` (dict of name → config with URL, model, key env var). `backends_constants.py` holds capability lists (`CODE_CAPABLE_BACKENDS`, `VISION_BACKENDS`, `THINKING_BACKENDS`, etc.). Detection helpers (`detect_vendor`, `detect_tier`, `detect_caps`) live in `backends.py` facade.

## Environment Variables

Copy `.env.example` to `.env`. Critical vars:
- `LIMA_ADMIN_TOKEN` — admin panel auth
- `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_TOKEN` — nuclear fallback backend
- Provider API keys: `CLAUDE_API_KEY`, `DEEPSEEK_API_KEY`, `NVIDIA_API_KEY`, etc.
- Feature flags: `GITEE_WEBHOOK_ENABLED`, `GITHUB_WEBHOOK_ENABLED`, `SEARXNG_ENABLED`, etc. (default off)
- `LIMA_DEVICE_TOKENS` — device gateway per-device auth

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

Docker health check: `curl -f http://localhost:8080/health`

## Git Conventions

- **Never** `git add .` — only stage milestone-related files
- **Never** commit `.env`, tokens, VPS passwords, `.lima-data/`, generated caches, reference repos
- **Never** stage `.claude/`, temp debug scripts, or credentials
- Use conventional commits (e.g., `feat:`, `fix:`, `refactor:`)
- Push to both GitHub (`origin`) and Gitee mirror (`gitee`)
- Working tree may contain unrelated user changes — do not `git reset` or `git checkout`

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
