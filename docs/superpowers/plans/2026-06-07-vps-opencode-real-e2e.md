# VPS OpenCode Real E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the current LiMa backend to VPS and validate it with a real OpenCode CLI end-to-end run, not simulated HTTP requests.

**Architecture:** Keep the production route unchanged: FastAPI routes feed `routing_engine.route()`, which selects backends and calls `http_caller`. Deployment uses the existing VPS scripts and systemd service. Real E2E validation must invoke `opencode` CLI against `https://chat.donglicao.com/v1` and then confirm server-side evidence.

**Tech Stack:** Python 3.10, FastAPI, pytest, ruff, Paramiko/SFTP deploy scripts, systemd on VPS, OpenCode CLI 1.16.2.

---

### Task 1: Local Quality Gate

**Files:**
- Read: `AGENTS.md`
- Read: `scripts/deploy_unified.py`
- Read: `scripts/vps_opencode_e2e_verify.py`
- Read: `scripts/opencode_e2e_real.py`
- Modify only if needed: files reported by ruff or focused tests

- [x] **Step 1: Run ruff on the current worktree**

Run:
```powershell
ruff check .
```
Expected: pass before deployment. If it fails on small style-only issues, fix those files and rerun.

- [x] **Step 2: Run focused local tests**

Run:
```powershell
.venv310\Scripts\python.exe -m pytest tests\test_routing_engine.py tests\test_opencode_e2e.py tests\test_opencode_round3.py tests\test_opencode_prompt_cache.py tests\test_opencode_provider_namespace.py -q --tb=short
```
Expected: pass before deployment.

### Task 2: VPS Deployment

**Files:**
- Use: `scripts/deploy_unified.py`
- Use: `scripts/deploy_vps_bundle.py` if full bundle deployment is required

- [x] **Step 1: Deploy current code to VPS**

Original draft command:
```powershell
.venv310\Scripts\python.exe scripts\deploy_vps_bundle.py
```
Expected: files upload successfully and `lima-router.service` restarts cleanly.

Actual: used `scripts/deploy_unified.py` because repo guidance says unified
deploy restarts through systemd and the bundle script has stale process-control
behavior. Both deploys completed with `Health: OK`.

- [x] **Step 2: Confirm service health on VPS**

Run local HTTPS smoke and remote systemd checks:
```powershell
curl.exe -sf https://chat.donglicao.com/health
```
Expected: JSON status `ok`.

### Task 3: Real OpenCode CLI E2E

**Files:**
- Use: installed `opencode` CLI
- Use: repo-local OpenCode config if present
- Read: `.lima-code/settings.json`

- [x] **Step 1: Verify OpenCode CLI installation**

Run:
```powershell
opencode --version
```
Expected: prints a real OpenCode version.

- [x] **Step 2: Run OpenCode CLI against LiMa VPS**

Run a non-interactive OpenCode CLI prompt configured to use LiMa endpoint and model. The command must execute `opencode`, not a Python OpenAI SDK request.

Expected: OpenCode returns an answer through LiMa.

Actual command shape:
```powershell
$env:OPENAI_BASE_URL='https://chat.donglicao.com/v1'; $env:OPENAI_API_KEY=$env:LIMA_API_KEY; opencode run --model lima/lima-1.3 --format json "..."
```

Final response text:
```text
LIMA_OPENCODE_E2E_OK_20260607
STREAM_TIMEOUT_FIX_CONFIRMED
```

- [x] **Step 3: Verify server-side evidence**

Use VPS logs or request traces to confirm the request reached LiMa with OpenCode identity and used the OpenCode path.

Expected: logs/traces show OpenCode request handling, backend selection, and no crashbacks.

Actual: VPS `lima-router.service` was active, `/health` returned `status=ok`,
startup log included `direct_stream_read_timeout=180s`, and post-restart
journal entries showed `/v1/responses` 200 OK with no new `ReadTimeout` or
ASGI exception in the filtered window.

### Task 4: Report

**Files:**
- Optional update: `findings.md` with concise evidence if deployment succeeds

- [x] **Step 1: Summarize commands and outcomes**

Include local gates, deploy result, VPS health, real OpenCode CLI command, and server-side evidence.

- [x] **Step 2: Record failures plainly**

If a step fails, include the exact failing command, failure type, and next action.

Observed failure during real E2E: the first longer OpenCode run exposed a
server-side `httpx.ReadTimeout` in `routes/opencode_direct_stream.py`, because
the preferred backend fell back to a 30 second registry timeout. Fixed by adding
`LIMA_OPENCODE_DIRECT_STREAM_READ_TIMEOUT` with a 180 second default floor and
deploying `opencode_config.py` plus `routes/opencode_direct_stream.py`.
