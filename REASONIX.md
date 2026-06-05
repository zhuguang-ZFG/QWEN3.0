# REASONIX.md — LiMa Project

> Updated: 2026-06-05. 31 milestones. smart_router migration COMPLETE (Slice 1-6 done).

## Key Facts (2026-06-05)

- **31 milestones** (M0–M11f + M-OC0–M-OC13) — decouple, OpenCode, cleanup, security, agent
- **LOCAL_ONLY_BACKENDS = empty** — all 184 backends cloud-native
- **5 VPS reverse sidecars** — scnet-large (4505), kimi (4504), longcat (4506), mimo (4507)
- **smart_router** — ✅ **迁移完成**（Slice 1-6）。255行→93行废弃壳。新增 `routing_constants.py` + `local_router.py`。CI gate 禁止新 `import smart_router`
- **LIMA_PERIODIC_CODING_EVAL=1** — VPS 周期编码 eval
- **API Key** — 4 脚本去硬编码 + 生产 key 环境变量 `LIMA_API_KEY`
- **OpenCode 适配** — error adapter (HTML/timeout) + normalizer (Bedrock/sdkKey) + session options + provider remap + `/v1` endpoint
- **Agent 能力** — doom loop + output truncation + step checkpoint
- **模型列表** — 13→21（+gpt-5, o3-mini, deepseek-r1, qwen3-235b, gemini-2.5-pro, mistral-large, codestral, mimo-v2.5-pro）
- **管理面板** — admin_api 路由修复，15 端点可用
- **死代码** — -5874 行 + 42 __pycache__ 目录清理

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

- **routing_engine.route()** is the authoritative routing module
- smart_router is a **deprecated re-export shell** (93 lines, Slice 6); CI-gated against new imports
- router_v3 provides P2C/sticky session features
- http_caller (httpx) is authoritative for HTTP
- routing_constants.py holds ROUTE/PUBLIC_MODEL_NAME (Slice 5)
- local_router.py holds call_local/warmup_router_model (Slice 4)
- distill_queue.py handles Q&A logging (Slice 3)
- routing_facade.py is the classify/intent/status gateway (Slice 1)

## New modules (M-OC8–M-OC13)

| Module | Purpose |
|------|------|
| `routing_constants.py` | ROUTE table + PUBLIC_MODEL_NAME (Slice 5) |
| `local_router.py` | call_local + warmup_router_model (Slice 4) |
| `tool_guard.py` | Doom loop detection + tool output truncation |
| `step_checkpoint.py` | Per-step agent checkpointing |
| `distill_queue.py` | Q&A distillation queue (extracted from smart_router) |
| `coding_pool_admission.py` | Eval evidence gate for IDE coding pool |
| `routing_facade.py` | smart_router → routing_engine migration gateway |
| `tool_repair_pipeline.py` | Tool call repair pipeline |
| `context_injection_trace.py` | Context injection tracing |
| `opencode_error_adapter.py` | Context overflow detection + SSE error parsing |
| `opencode_message_normalizer.py` | Message normalization (Bedrock/sdkKey/surrogate) |
| `reasoning_variants.py` | Reasoning effort → provider-specific body params |
| `session_options.py` | Per-model session options injection |

## Watch out for
- **Dockerfile references `requirements.txt`** but actual file is `requirements_server.txt`
- **`.env` mandatory** — `LIMA_API_KEY` must be set or startup errors
- **FastAPI 0.136.3 blocked** — malicious PyPI release, pinned `<0.136.3`
- **`server.py` patches `sys.path`** before other imports
- **`deepcode-cli/`, `esp32S_XYZ/`, `opencode-source/`** are separate sub-projects
- **部署**：`deploy_opencode.py` 用 `fuser -k 8080/tcp` 杀旧进程，然后 `python server.py` 启动
- **OpenCode 客户端配置**：需要 `"api"`（URL 字符串）+ `"npm"` + `"options"` + `"env"` + `"models"` 才能被识别
