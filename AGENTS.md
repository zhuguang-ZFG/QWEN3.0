# AGENTS.md

OpenCode sessions should use this as the compact repo guide. For full history, read `STATUS.md`; for pipeline ownership, read `docs/REQUEST_PIPELINE_AUTHORITY.md`.

## Repo Identity

- LiMa is a personal AI coding assistant backend, not a commercial platform. Do not reintroduce payment, public registration, customer billing, or commercial dashboard work unless explicitly requested.
- Runtime is Python 3.10 + FastAPI on port `8080`; primary clients are OpenCode/IDE and Telegram.
- The API is OpenAI-compatible at `/v1/chat/completions` and Anthropic-compatible at `/v1/messages`.
- Backend inventory is cloud-first and lives in `backends_registry.py` plus `backends_constants.py`; `LOCAL_ONLY_BACKENDS` is intentionally empty per `STATUS.md`.

## Commands

- Install server deps: `pip install -r requirements_server.txt`.
- Run local server: `python server.py` or `python -m uvicorn server:app --host 0.0.0.0 --port 8080`.
- Use project venv on Windows when possible: `.venv310\Scripts\python.exe -m pytest ...`.
- Full pytest suite: `pytest --tb=short -q`.
- Full suite without CI gates: `python -m pytest tests/ -q --ignore=tests/test_ci_gates.py`.
- Single file: `pytest tests/test_routing_engine.py -v`.
- Single test: `pytest tests/test_http_caller_concurrency.py::test_concurrent_calls -v`.
- Skip offline RAG eval fixtures: `pytest -m "not rag_gate"`.
- Lint: `ruff check .`.
- Format check: `ruff format --check`; format: `ruff format .`.
- Type check: `pyright`.
- Smoke after server start: `curl -sf http://127.0.0.1:8080/health` and `curl -sf http://127.0.0.1:8080/v1/models | python -m json.tool`.
- Docker: `docker compose build`, `docker compose up -d`, `docker compose down`; compose also starts SearXNG on host `8081`.
- PowerShell note: use `;` or `if ($?) { ... }`; do not write Unix-style `&&` chains.

## Test And CI Facts

- `pytest.ini` sets `testpaths = tests`, `pythonpath = .`, and `asyncio_mode = auto`; root-level `test_*.py` files are not in the default pytest suite.
- CI in `.github/workflows/test.yml` runs `ruff check .`, then `bandit -r agent_runtime/ routes/ -ll`, then `pytest --tb=short -q`.
- `pyrightconfig.json` is local guidance, not in CI; it checks selected production paths and excludes `tests`, `scripts`, `data`, `deepcode-cli`, and other external/local trees.
- Ruff targets Python 3.10, line length 120, and only gates selected high-signal rules; do not assume broad style linting is active.

## Production Request Path

- Real chat path is explicit, not `context_pipeline.factory`: `server.py` → `routes/chat_endpoints.py` / `routes/anthropic_messages_handler.py` → `routes/chat_preflight.py` → `routing_engine.route()` → `http_caller` → `route_post_process.py` / `response_cleaner.py` → `routes/chat_post_closeout.py`.
- `routing_engine.route()` is the backend-selection authority. It classifies, injects retrieval/web/code context, injects skills, handles OpenCode prompts, selects backends, compresses context, executes fallback, validates coding answers, and returns metadata.
- `context_pipeline.factory.build_default_pipeline()` is a lab/test harness, not the live production owner.
- `routes/route_registry.py` centrally mounts routers via `RouteRegistryDeps`; `server.py` wires dependencies explicitly with `inject_state()` / `inject_deps()`, not FastAPI `Depends`.

## Module Ownership

- `backends.py`, `http_caller.py`, `health_tracker.py`, and `agent_runtime/orchestrator.py` are facade-style modules. Check whether a file is a re-export facade before adding logic.
- Prefer `http_caller` / `http_sync` / `http_async` / `http_stream` for backend calls. `router_http.py` is legacy urllib path.
- Prefer `health_tracker.py` over `router_circuit_breaker.py` for health and cooldown logic.
- `smart_router.py` is legacy utility/compat code; do not make it the new production authority.
- `routes/quality_gate*.py` and root `quality_gate.py` are different concerns; avoid mixing route retry logic with coding eval helpers.
- `session_memory/store*.py` is split by db/crud/promote/admin responsibilities; do not collapse it back into one store file.
- `agent_runtime/` is not on the chat hot path. Keep agent execution, shell/git/network permissions, audit, and task queue isolated from `routing_engine`.

## OpenCode-Specific Gotchas

- OpenCode tuning constants are read at import time in `opencode_config.py`; changing `LIMA_OPENCODE_*` env vars requires process restart.
- Default OpenCode tool mode is `LIMA_OPENCODE_TOOL_MODE=direct`; this keeps OpenAI-format tools on the direct routing path.
- OpenCode overflow behavior is guarded by `opencode_error_adapter.py`; preserve HTTP 413 and SSE error semantics.
- `.lima-code/settings.json` is the repo-local OpenCode/LiMa IDE reference. There is no root `opencode.json` in this repo.
- `opencode-source/` is a gitignored upstream reference clone used for parity checks; do not treat it as LiMa source.

## Environment And Secrets

- `.env` must define `LIMA_API_KEY` or `LIMA_API_KEYS`; server startup should fail rather than silently degrade when required auth is missing.
- Never hardcode provider keys or tokens in production code; use environment variables.
- Do not commit `.env`, local DBs, generated caches, `.lima-data/`, credentials, VPS secrets, `.claude/`, `.qoder/`, or temp debug scripts like `_*.py`.
- New capabilities should default off behind explicit `LIMA_` env flags unless the repo already documents them as on.

## Coding Rules That Matter Here

- Target files under 300 lines and functions under 50 lines. If a touched file is already oversized, prefer focused extraction over adding more logic.
- No silent degradation on production paths. `except Exception: pass` is forbidden; log at least a warning with exception type/reason.
- Avoid local imports inside functions unless needed for optional dependencies; local `from X import Y` can shadow module-level names and cause `UnboundLocalError`.
- Async code must not use `time.sleep()`; use `asyncio.sleep()` or `asyncio.to_thread()`.
- New shared modules should avoid global mutable state and expose `inject_state()` / `inject_deps()` if runtime state is needed.
- Keep changes minimal. Do not add backward-compatibility layers unless persisted data, shipped behavior, or external consumers require them.

## Deployment And Git

- Deploy conventions live in `docs/DEPLOY_AND_RELEASE_CONVENTION.md`; do not claim VPS deployment without real VPS health/smoke evidence.
- GitHub push to `main` triggers CI and then Docker/GHCR deploy to VPS with rollback in `.github/workflows/deploy.yml`.
- Manual deploy scripts exist, especially `scripts/deploy_unified.py`, `scripts/deploy_vps_bundle.py`, and slice-specific deploy scripts.
- Before any requested commit, inspect `git status`, `git diff`, and recent log. Stage only files related to the requested change; never use `git add .`.
- Working tree may contain unrelated user/agent changes. Do not revert, reset, checkout, or modify unrelated changes unless explicitly asked.
- Do not amend commits, force-push, or create PRs unless explicitly requested.

## Documentation Authority

- `STATUS.md` is current state and milestone evidence.
- `docs/REQUEST_PIPELINE_AUTHORITY.md` is the authoritative request-pipeline/module-ownership reference.
- `docs/DEPLOY_AND_RELEASE_CONVENTION.md` is the deploy/closeout reference.
- `docs/EXTERNAL_REPOS.md` explains decoupled local clones such as `deepcode-cli`, `esp32S_XYZ`, and `opencode-source`.
- `docs/archive/` contains historical plans. Do not use archived roadmap docs for current priority decisions.
