# GEMINI.md

Instructional context and rules for AI assistant operations in the LiMa repository.

## 1. Project Overview

**LiMa（力码）** is an AI Smart Device Unified Cloud Service Platform developed by Shenzhen Donglicao Technology (www.donglicao.com). Originally designed as a personal coding assistant backend, the project underwent a complete strategic transformation in June 2026 to focus entirely on providing a unified cloud brain for AI smart hardware devices (such as ESP32 drawing and writing machines).

### Core Capabilities:
- **Intelligent Understanding**: Translating natural language requests into device-executable drawing or writing tasks.
- **Task Orchestration**: SVG path generation, rendering, path optimization, and G-code creation.
- **Device Gateway**: MQTT/WebSocket bi-directional real-time communication for device monitoring and task delivery.
- **Multi-Model Routing**: Intelligent model selection, routing, and load balancing across 170+ backends (via OpenRouter, OpenAI, and local models) with fallback execution and health tracking.
- **API Interfaces**: Offers OpenAI-compatible chat endpoints (`/v1/chat/completions`) and legacy `xiaozhi-v1` compat endpoints mapping App client operations to LiMa models.

---

## 2. System Architecture

```text
小程序 / App / Web 控制台
            │ HTTPS / WebSocket
            ▼
    FastAPI (LiMa Core)
   ┌────────┴────────┐
   │    API Layer    │  ← routes/route_registry.py (Chat & Device Gateway)
   └────────┬────────┘
   ┌────────┴────────┐
   │ Business Logic  │  ← routing_engine.py / router_v3.py (AI Routing)
   │                 │  ← svgpathtools / shapely / pypotrace (Drawing Engine)
   └────────┬────────┘
   ┌────────┴────────┐
   │ Infrastructure  │  ← SQLite (WAL, Foreign Keys) / Redis / MQTT / Prom
   └────────┬────────┘
            │ MQTT / WebSocket
            ▼
   ESP32 Devices (Drawing / Writing Machines)
```

### Request Pipeline (Production Chat)
The live production chat request pipeline is explicit, layered, and strictly defined. Ref: `docs/REQUEST_PIPELINE_AUTHORITY.md`.

1. **Edge**: `server.py` → `BodySizeLimitMiddleware` → `access_guard`
2. **Protocol Routes**: `routes/chat_endpoints.py` / `routes/anthropic_messages_handler.py`
3. **Preflight**: `routes/chat_preflight.py` / `server_context.py` (guardrails, budget, identity)
4. **Routing Engine**: `routing_engine.route()`
   - `identity_guard` (short-circuit checks)
   - `classify` (request type: ide, chat, code, image) and `classify_scenario` (scenario: coding, chat, device, etc.)
   - `skill_store` (long-term memory/routing lesson recall)
   - `retrieval_injection` (knowledge graph / vector RAG context injection)
   - `code_context` (tree-sitter code scanning, coding-only)
   - `select_backends` / `routing_selector.select` (cooldown, budget, weights selection)
   - `skills_injector` (inject system-prompt skills into message list)
   - `speculative` (parallel speculative calls for simple requests)
   - `routing_executor.execute` (sequential execution + fallback logic)
   - `response_validator` (response quality validation, coding-only)
   - `route_post_process` (correlation, evidence and feedback logging)
5. **HTTP Transport**: `http_caller.py` → `http_sync` / `http_async` / `http_stream` (httpx stack)
6. **Post-Process / Closeout**: `routes/chat_post_closeout.py` (memory write, telemetry metrics, distill queue)

---

## 3. Building, Running, and Testing

All commands must be executed from the repository root `D:\QWEN3.0` (using PowerShell).

### Setup and Start
```powershell
# 1. Install Dependencies
pip install -r requirements_server.txt

# 2. Configure Environment Variables
# Copy .env.example to .env and configure LIMA_API_KEY (mandatory)
copy .env.example .env

# 3. Start the Server Locally
python -m uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

### Verification & Testing
```powershell
# Run the complete pytest suite (quiet & short traceback)
python -m pytest --tb=short -q

# Run specific test files
python -m pytest tests/test_routing_engine.py -v
python -m pytest tests/test_device_gateway_routes.py -v

# Run specific test matching name
python -m pytest tests/test_routing_engine.py -k "test_classify_ide" -v

# Full pre-commit CI simulation
python scripts/run_pre_commit_check.py --full
```

### Static Analysis & Styling
```powershell
# Linting checks
ruff check .

# Formatting checks and auto-formatting
ruff format --check
ruff format .

# Type checking specific core entry points
pyright server.py routing_engine.py
```

### Docker & Infrastructure
```powershell
# Build and run Docker containers
docker compose build
docker compose up -d
```

---

## 4. Development Conventions & Code Quality Red Lines

To maintain the high quality and performance of the LiMa cloud platform, every change must strictly respect the following boundaries:

### Core "Superpowers" Principles
1. **Document First**: Any non-trivial modification requires updating or creating design docs under `docs/` beforehand. Documentation must be in **Chinese**, while code, logs, and variables remain in English.
2. **File Size and Focus**: Keep files focused and cohesive. A single module file should ideally target **≤300 lines**, and any single function should target **≤50 lines**. Split files immediately when they exceed 300 lines.
3. **Never Break Production**: Keep new features or integrations parallel and decoupled from the main hot-paths until they are fully proven via unit tests and local smoke runs. Ensure all changes are reversible.
4. **Workspace Hygiene**: Keep temporary local DB files, external references, FRP tools, and deployment tarballs in `D:\LIMA-external\` to ensure the workspace remains clean. (Ref: `docs/WORKSPACE_HYGIENE.md`).

### Coding Red Lines
- **No silent/degraded error handling**: Empty/bare `except Exception: pass` blocks are **STRICTLY PROHIBITED**. At a minimum, capture and log warnings with explicit exception class types (`logger.warning` or `logger.exception`).
- **No hardcoded secrets**: Never commit API keys or secret credentials in the repository. Use environment variable lookups.
- **Graceful Optional Import Handling**: Handle optional dependencies using try/except blocks checking for `ImportError`. Log debug statements if the package is missing, rather than allowing the master server to crash on boot.
- **Mandatory Configuration**: The `.env` file must define `LIMA_API_KEY`; the server will raise a startup error if it is missing.
- **No warnings or type suppression**: Avoid code bypasses, casts (TypeScript equivalents in Pyright), or silent suppression of typing/linter errors. Address them explicitly and idiomatically.

### Milestone Collaboration Protocol
Owner implements → AI reviews, refactors, and runs the comprehensive test suite locally → Update `progress.md`/`findings.md`/`STATUS.md` → Stage only relevant files → Commit → Push to `origin`.

---

This instruction file represents the authoritative configuration, style, and operational rules for the LiMa project. All subsequent tasks must adhere to these directives.
