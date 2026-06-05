# REASONIX.md — LiMa Project

> Updated: 2026-06-01. 184 backends all cloud-native. LiMa CLI initialized.

## Key Facts (2026-06-01)

- **13 milestones completed** (M0–M11d) — decouple from local host + ModelScope + cache-first port
- **LOCAL_ONLY_BACKENDS = empty** — all 184 backends cloud-native
- **FRP / DuckAI / deepseek_free** — stopped and removed from VPS
- **ModelScope** — 8 backends active (ms_deepseek_v4/qwen35/kimi_k25/glm5 + code variants)
- **LiMa CLI** — v0.1.25, ContextManager ported (+412 lines), 498/507 tests pass
- **LOCAL_ONLY_BACKENDS = empty** — all backends are cloud-native (M1-M7)
- **5 VPS reverse sidecars active** — scnet-large (4505), kimi (4504), longcat (4506), mimo (4507)
- **LiMa CLI** — lima v0.1.24, submodule at `deepcode-cli/`, smoke-tested
- **ESP32 / WeChat / FRP tunnels** — retired

## Stack
- **Python 3.10+** (ruff, Dockerfile, pyrightconfig)
- **FastAPI + Uvicorn** — port 8080, OpenAI-compatible API
- **httpx** — async HTTP client for reverse backends
- **ruff** — linter + formatter (`ruff.toml`, line-length 120)
- **pytest** — asyncio_mode=auto, testpaths=tests
- **pyright** — type checker, basic mode (`pyrightconfig.json`)
- **Docker Compose** — prod deploy (+ optional SearXNG)

## Layout
| Dir | Content |
|-----|---------|
| `server.py` | FastAPI entry point |
| `routes/` | 70+ route modules (chat, anthropic, telegram, admin, devices) |
| `agent_runtime/` | Agent orchestration — queue, worker, executor, approvals |
| `session_memory/` | Session persistence — SQLite facade |
| `context_pipeline/` | Code retrieval + injection pipeline |
| `channel_gateway/` | Telegram bot + channel integrations |
| `device_gateway/` | IoT gateway — MQTT/WS transport |
| `tests/` | pytest suite (~135 files), fixtures in `tests/fixtures/` |
| `scripts/` | Ops/deploy/probe scripts — `deploy_unified.py`, cookie provisioning |
| `deploy/` | Systemd units, CF workers, reverse proxy templates |
| `data/` | Runtime SQLite DBs + eval results (don't edit by hand) |
| `docs/` | Design docs, quality plans, release conventions |
| `deepcode-cli/` | Separate Node.js CLI client, excluded from Python tooling |

## Commands
```
make test        # pytest --tb=short -q && ruff check .
make lint        # ruff check . && ruff format --check
make format      # ruff format .
make deploy      # python scripts/deploy_unified.py
make docker-build / docker-up / docker-down
make smoke-test  # curl health + /v1/models
```
Dev: `python -m uvicorn server:app --host 0.0.0.0 --port 8080`

## Conventions
- **Line length 120** (ruff), not Black's 88
- **Ruff rules**: E9 (syntax), F82x (undefined names), B005/B011/B012/B905 (bugs), S507 (SSH)
- **Tests in `tests/`**, not colocated; pattern `test_<module>.py`
- **`__init__.py` + facade modules** (`smart_router.py`, `backends.py`, `routing_engine.py`, `http_caller.py`) allow F401
- **Dual routing**: `routing_engine.py` (five-layer) ↔ `smart_router.py` (compat); see `docs/REQUEST_PIPELINE_AUTHORITY.md`
- **FastAPI lifespan** in `server_lifespan.py` (not inline)

## Architecture notes (from docs/REQUEST_PIPELINE_AUTHORITY.md)

- **routing_engine.route()** is the authoritative routing module — NOT smart_router or router_v3
- smart_router is a legacy compat layer (26 callers), delegates to routing_engine
- router_v3 provides P2C/sticky session features that complement routing_engine
- http_caller (httpx) is authoritative for HTTP; router_http (urllib) is legacy
- health_tracker is authoritative for health/cooldown; circuit_breaker is legacy

## Watch out for
- **Dockerfile references `requirements.txt`** but actual file is `requirements_server.txt`
- **`.env` mandatory** — `LIMA_API_KEY` must be set or startup errors
- **FastAPI 0.136.3 blocked** — malicious PyPI release, pinned `<0.136.3`
- **`server.py` patches `sys.path`** before other imports
- **`deepcode-cli/`, `esp32S_XYZ/`** are separate sub-projects, excluded from Python tooling
- **~150 top-level .py files** — many are eval/probe/ops scripts, not all import-safe
