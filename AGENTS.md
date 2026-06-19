# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Project Overview

LiMa is a multi-backend AI routing server (Python 3.10 + FastAPI) that provides an OpenAI/Anthropic-compatible API. It intelligently routes requests across 170+ AI backends (Groq, NVIDIA, OpenRouter, DeepSeek, Cloudflare, etc.) based on request type, health, budget, and quality scoring. Serves as the cloud platform for AI drawing/writing devices (ESP32-based smart hardware).

**Public endpoint:** `https://chat.donglicao.com` (VPS nginx → :8080)

## Common Commands

```powershell
# Run all tests
python -m pytest --tb=short -q

# Run a single test file
python -m pytest tests/test_routing_engine.py -v

# Run a single test by name
python -m pytest tests/test_routing_engine.py -k "test_classify_ide" -v

# Full CI-style test (with long/external tests ignored)
python scripts/run_pre_commit_check.py --full

# Lint
ruff check .

# Format check / auto-format
ruff format --check
ruff format .

# Type checking (specific files)
pyright server.py routing_engine.py

# Start server locally
python -m uvicorn server:app --host 0.0.0.0 --port 8080

# Docker
docker compose build
docker compose up -d

# Smoke test (local)
curl -sf http://127.0.0.1:8080/health

# Deploy to VPS
python scripts/deploy_unified.py

# Deploy Chat Web static files to VPS
python scripts/deploy_chat_web.py

# Repo stats
python scripts/repo_stats.py
```

## Architecture

### Request Pipeline (Production)

```
Client → server.py (BodySizeLimitMiddleware, access_guard)
      → routes/chat_endpoints.py
      → routes/chat_preflight.py (guardrails, budget, identity)
      → routing_engine.route()          ← authoritative routing entry
         ├─ identity_guard              (identity short-circuit)
         ├─ routing_classifier.classify (request_type: ide/chat/code/image)
         ├─ routing_classifier.classify_scenario (scenario: coding/chat/device/...)
         ├─ skill_store recall          (skill memory → recalled_backend)
         ├─ context_pipeline.retrieval_injection (knowledge graph/vector context)
         ├─ code_context_injection      (coding only: tree-sitter scan)
         ├─ router_v3.select_backends → routing_selector.select (backend ranking)
         ├─ skills_injector             (inject skills into messages)
         ├─ speculative                 (simple requests: parallel speculative call)
         ├─ routing_executor.execute    (sequential/parallel + fallback)
         ├─ response_validator          (coding: quality validation + retry)
         └─ route_post_process          (correlation/evidence/feedback)
      → http_caller → backend pool (httpx sync/async/stream)
      → routes/chat_post_closeout.py (memory, metrics, distill queue)
      → Client (JSON or SSE)
```

Authority doc: `docs/REQUEST_PIPELINE_AUTHORITY_CN.md`（中文权威版；英文归档已删除）

### Key Module Ownership

| Concern | Module | Legacy/Facade |
|---------|--------|---------------|
| Backend registry | `backends_registry.py` + `backends_constants.py` | `backends.py` re-exports |
| Intent analyze | `routing_intent.py` | — |
| Intent classify | `routing_classifier.py` | — |
| Backend pools | `router_v3/` package (`POOLS` in `pools.py`) | — |
| Backend ranking | `routing_selector/` package | — |
| Backend execution | `routing_executor.py` | — |
| HTTP transport | `http_caller.py` (→ `http_sync`/`http_async`/`http_stream`) | — |
| Health/cooldown | `health_tracker.py` | — |
| Budget | `budget_manager.py` | — |
| Sticky session | `sticky_session.py` | — |
| Stream bridge | `streaming.py`, `routes/stream_handlers.py` | — |
| Retrieval inject | `context_pipeline/retrieval_injection.py` | — |
| Code context | `context_pipeline/code_context_injection.py` | — |
| Skills inject | `skills_injector.py` | — |
| Session memory | `session_memory/store*.py` (split: db/crud/promote/admin) | — |
| Ops metrics | `routes/ops_metrics.py` | — |

### Parallel Subsystems (Non-Chat Hot Path)

| Subsystem | Path | Purpose |
|-----------|------|---------|
| Device Gateway | `device_gateway/`, `routes/device_gateway*.py` | `/device/v1/*`; Redis task queue + WSS; ESP32/hardware |
| Channel Gateway | `channel_gateway/`, `routes/channel_gateway.py` | Slash commands, G3 sessions |
| Session Memory | `session_memory/` | Persistent memory + learning loop |
| Context Pipeline | `context_pipeline/` (43 modules) | Retrieval, code context, validation, reranking |
| Observability | `observability/` | Prometheus metrics, structured logging |
| Provider Probe | `packages/provider-probe-offline/provider_probe/`（Cold 离线；根 `provider_probe/` 为指针）, `provider_automation/`, `backends_registry/` | Auto-discovery of new AI providers (JDCloud only) |

### Server Bootstrap

- `server.py` — thin FastAPI entry; wires middleware, injects deps, registers routes via `routes/route_registry.py`
- `server_bootstrap.py` — model constants (`MODEL_ID = "lima-1.3"`), runtime state, Cloudflare last-resort fallback
- `server_lifespan.py` — async lifespan: loads health state, backend profiles, starts probe loop, coding eval, session memory daemon, MQTT, Prometheus exporter, auto-indexer

### Deployment Topology

```
Internet → VPS (nginx → lima-router :8080, Redis)
              ↕ FRP :8088
         Windows local (:8080 dev proxy + free backends)
```

- Primary VPS: `47.112.162.80` (Alibaba Cloud)
- Secondary node: JDCloud `117.72.118.95` (provider probe/monitoring only)
- Deploy scripts: `scripts/deploy_unified.py` (capacity-aware, auto-backup)
- Rollback: `/opt/lima-router/backups/`

## Tech Stack

- **Runtime:** Python 3.10 + FastAPI + uvicorn
- **HTTP client:** httpx
- **Data:** SQLite (semantic cache, session memory), Redis (device tasks)
- **Linting:** ruff (config in `ruff.toml`, target py310, line-length 120)
- **Type checking:** pyright
- **Testing:** pytest (asyncio_mode=auto, testpaths=tests)
- **Container:** Docker multi-stage (python:3.10-slim)
- **Container:** Docker multi-stage (python:3.10-slim)

## Code Quality Rules

### Hard Rules (Superpowers)

1. **No silent degradation** — no `except Exception: pass` or `except ImportError: pass` in production paths. Must at minimum `logger.warning` with reason. Critical deps (chromadb, tree-sitter) must log clear warnings at startup, not silently degrade at runtime.
2. **No auto-downgrade verification** — VPS deploys must be verified on real VPS, not just localhost. Public APIs tested via real domain with real tokens.
3. **.env merge, not overwrite** — deploy must backup VPS `.env` first, append new vars, never `sftp.put` overwrite.
4. **Telegram retired** — do not re-register `/telegram` routes, webhooks, or outbound notifications.

### Documentation Language

- **文档类产物必须使用中文**：新增或更新 `docs/**/*.md`、根部说明文档、计划、状态、进展、报告、runbook、PRD、架构说明和交接文档时，默认使用中文撰写。
- 保留必要的英文代码标识、命令、API 字段、日志片段、协议字段、文件名、路径、提交信息和外部专有名词。
- 如果修改既有英文文档，不要求一次性全文翻译，但本次新增段落和后续文档类增量必须优先使用中文。

### Size Constraints

- Single file target: ≤300 lines
- Single function target: ≤50 lines
- New modules over 300 lines must be split

### What NOT to Use for New Code

| Module | Status |
|--------|--------|
| `context_pipeline.factory` as sole pipeline | Lab/test harness only |

## Development Workflow

```
1. Design doc (docs/*.md) for non-trivial changes
2. Local coding
3. pytest (focused → full for production changes)
4. ruff check + pyright on touched files
5. VPS deploy + health/smoke verification (scripts/deploy_unified.py)
6. Update STATUS.md / progress.md / findings.md
7. git commit (conventional, only milestone files) → push origin → push gitee
```

## Git Rules

- **Never** use `git add .` — only stage milestone-related files
- Never stage `.claude/`, reference repos, temp debug scripts, credentials, `.env`, `.lima-data/`
- Never commit real keys, VPS passwords, or API tokens
- Never force-push or reset without explicit user permission
- Workspace may contain user changes; do not `git reset` or `git checkout` casually

## Milestone Collaboration Protocol

1. Owner implements milestone slice
2. Agent reviews code, runs focused tests → full tests → `git diff --check`
3. Agent updates `progress.md` / `findings.md` with closeout evidence
4. Agent stages only related files, commits (conventional), pushes to GitHub (`origin`) + Gitee (`gitee`)
5. Only after push does agent propose next milestone

**Auto-closeout** (when user hasn't said "don't deploy/commit"): local pytest → VPS deploy + restart + health/smoke → update docs → git add/commit/push.

## ECC 开发流程（增量采用）

> 参考 [`reference/ECC`](./reference/ECC)（Everything Claude Code）的跨 harness 工程实践，按 LiMa 现状做增量裁剪。ECC 流程优先于通用建议，但低于本文件「Hard Rules」和用户的直接指令。

核心要求：

1. **Plan First**：非平凡改动先计划，用户批准后执行。
2. **TDD**：RED → GREEN → REFACTOR；提交前 focused → full tests。
3. **Code Review**：自查无 secret、输入验证、错误不泄露、无静默吞异常、小文件/小函数、优先不可变。
4. **提交前**：`ruff`、`pyright`、`scripts/check_code_size.py`、文档同步、仅 stage 相关文件、conventional commits。
5. **安全响应**：STOP → 修复 CRITICAL → 轮换 secret → 检查同类问题 → 更新 `findings.md`。

完整清单见 [`docs/ECC_WORKFLOW_CN.md`](docs/ECC_WORKFLOW_CN.md)。

## Key Documents

| Document | Purpose |
|----------|---------|
| `STATUS.md` | Current project status |
| `CLAUDE.md` | Condensed dev rules + repo stats |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 18-step pipeline + module ownership matrix |
| `docs/ROUTING_ENGINE_DESIGN.md` | routing_engine.py design decisions |
| `docs/ARCHITECTURE.md` | System architecture |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | Deploy/release hard rules |
| `docs/LIMA_MEMORY_CN.md` | Long-term project memory |
| `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | Current optimization roadmap |
| `task_plan.md` | Current task plan + evidence |
| `findings.md` | Factual discoveries and ops conclusions |
| `progress.md` | Execution progress log |

## Environment Variables

See `.env.example` for full list. Critical:

- `LIMA_API_KEY` / `LIMA_API_KEYS` — required, server errors on missing
- `LIMA_ADMIN_TOKEN` — admin panel auth
- `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_TOKEN` — nuclear fallback backend
- `LIMA_DEPLOY_PASS` — VPS deploy password
- Feature flags default to off: `GITEE_WEBHOOK_ENABLED=0`, `GITHUB_WEBHOOK_ENABLED=0`, `SEARXNG_ENABLED=0`, `CODESEARCH_MCP_ENABLED=0`, etc.

## CodeGraph — Code Intelligence (preferred over GitNexus)

This repo uses **CodeGraph** for call-graph exploration, impact analysis, and dead-code audits. Index lives at `.codegraph/codegraph.db`. **Do not** use GitNexus hooks or `gitnexus_*` MCP tools here.

### Always do

- After pulling or large refactors: `codegraph sync .` (or `codegraph index .` if missing).
- Before editing unfamiliar symbols: CodeGraph MCP or `codegraph impact <symbol>`.
- Before deleting modules: `python scripts/codegraph_orphans.py --fanin` (graph + ripgrep; graph-only orphans may be lazy imports).

### Setup

| Task | Command |
|------|---------|
| MCP for all local agents | `pwsh -File scripts/setup_codegraph_agents.ps1` |
| LiMa MCP bundle (codegraph + context7 + fetch) | `pwsh -File scripts/setup_lima_mcps.ps1` |
| Per-project index | `codegraph index .` then `codegraph sync .` |

### References

- Orphan audit: `scripts/codegraph_orphans.py`
- Slimming evidence: `progress.md` (2026-06-15 CodeGraph entries)

## Ponytail（顾问规则，LiMa 优先）

本项目采用 [Ponytail](https://github.com/DietrichGebert/ponytail) 的「lazy senior dev」理念作为代码精简顾问。详情见 [`docs/AGENTS_PONYTAIL.md`](docs/AGENTS_PONYTAIL.md)。源文件位于 `reference/ponytail/`。
