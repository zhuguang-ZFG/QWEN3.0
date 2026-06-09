# LiMa Server Global Code Quality Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Close the current LiMa Server code-quality gaps found by the 2026-05-23 global review, without changing product direction or weakening existing safety boundaries.

**Architecture:** Treat this as a staged hardening pass, not a broad rewrite. First restore deterministic tests and remove credential hazards, then make routing/admission policy explicit, then reduce duplicated context/retrieval code and split the largest admin/server surfaces behind tested adapters.

**Tech Stack:** Python 3.11, FastAPI, pytest, existing LiMa modules under `server.py`, `routes/`, `routing_engine.py`, `router_v3.py`, `backends.py`, `session_memory/`, and `context_pipeline/`.

---

## Review Evidence

Scope included LiMa Server runtime, routes, tests, scripts, and local support modules:

- `server.py`
- `smart_router.py`
- `routing_engine.py`
- `router_v3.py`
- `http_caller.py`
- `backends.py`
- `routes/`
- `context_pipeline/`
- `session_memory/`
- `tool_gateway/`
- `scripts/`
- `tests/`

Scope excluded local reference repositories and LiMa Code:

- `deepcode-cli/`
- `bCNC/`, `opencode/`, `portkey-ref/`, `routellm-ref/`, and other downloaded reference trees
- `.claude/`
- generated DB files under `data/*.db`

Fresh verification:

```powershell
D:\GIT\venv\Scripts\python.exe -m compileall -q server.py routing_engine.py router_v3.py http_caller.py backends.py response_cleaner.py context_pipeline session_memory routes tool_gateway scripts tests
```

Result: passed.

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q --ignore=active_model
```

Result: `1 failed, 387 passed, 8 skipped`.

Failure:

```text
tests/test_admin_agent_audit.py::test_admin_agent_audit_returns_agent_tasks
expected 200, got 401
```

Reproduction proof:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_admin_agent_audit.py -q --ignore=active_model
```

Result: `2 passed`.

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_access_guard.py tests\test_admin_agent_audit.py -q --ignore=active_model
```

Result: `1 failed, 8 passed`.

Root cause class: `routes.admin._ADMIN_TOKEN` is captured at import time. `tests/test_access_guard.py` imports `routes.admin` before `tests/test_admin_agent_audit.py` sets `LIMA_ADMIN_TOKEN`, so the admin audit test becomes order-dependent. `routes.agent_tasks.py` already uses a runtime `_get_admin_token()` pattern; `routes.admin.py` should match it.

Largest files found:

| File | Lines | Risk |
|---|---:|---|
| `smart_router.py` | 1070 | old router surface still large |
| `server.py` | 955 | protocol boundary plus context stages still mixed |
| `routes/admin.py` | 655 | auth, APIs, HTML, JS, backend ops in one file |
| `tool_dispatcher.py` | 634 | likely should be reviewed before enabling broader autonomy |
| `routing_engine.py` | 580 | routing plus many context integrations in one path |
| `routes/agent_tasks.py` | 511 | task lifecycle state and route handlers together |

Security scan findings were redacted in the command output. Categories found:

- `backends.py:201-202` contains hardcoded MiMo TTS key-shaped literals.
- `mimo_tts.py:20` contains an environment variable fallback to a hardcoded key-shaped literal.
- root-level local debug/deploy/stress scripts contain hardcoded password-shaped literals and must not be staged.
- test files contain deliberate fake bearer/token strings for redaction tests; those should stay but be allowlisted by the scanner.

Other quality findings:

- `routes/admin.py` and `routes/telegram.py` still capture `LIMA_ADMIN_TOKEN` at import time, while `routes.agent_tasks.py` uses runtime lookup.
- `router_v3.py` includes `mimo_web*` and `longcat_web` in active pools, while `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` still says new web AI candidates start sandbox-only. This is a policy/documentation mismatch even if the user intentionally wants these backends in coding pools.
- Retrieval injection now exists in `routing_engine.route()` and in `routing_engine.inject_retrieval_context()`, but the logic is duplicated and has separate trace shapes.
- `server.py` now contains prompt memory recall, identity adaptation, token budget, thinking, streaming, fallback, post-response memory write, and distill/sys-prompt logging in one handler.
- `routes/telegram.py` uses deprecated FastAPI `@router.on_event("startup")`.
- Full pytest emits unawaited coroutine warnings around Telegram tests; warnings do not fail the suite today but weaken signal quality.

## Task 1: Fix Admin Auth Import-Order Failure

**Priority:** P0

**Files:**
- Modify: `routes/admin.py`
- Test: `tests/test_admin_agent_audit.py`
- Test: `tests/test_access_guard.py`

- [x] **Step 1: Write the failing import-order regression test**

Add this test to `tests/test_admin_agent_audit.py`:

```python
def test_admin_agent_audit_auth_uses_runtime_env_after_prior_admin_import(monkeypatch):
    import routes.admin as admin_routes

    monkeypatch.setattr(admin_routes, "_ADMIN_TOKEN", "")
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "runtime-admin-token")

    app = FastAPI()
    app.include_router(admin_routes.router)
    app.include_router(agent_router)
    local_client = TestClient(app)

    local_client.post("/agent/tasks", json={
        "repo": "D:/GIT/deepcode-cli",
        "goal": "runtime admin token",
        "allowed_tools": ["git_diff"],
        "mode": "review",
    }, headers={"Authorization": "Bearer runtime-admin-token"})

    resp = local_client.get(
        "/admin/api/agent-audit",
        headers={"Authorization": "Bearer runtime-admin-token"},
    )

    assert resp.status_code == 200
```

- [x] **Step 2: Run the failing test**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_access_guard.py tests\test_admin_agent_audit.py -q --ignore=active_model
```

Expected before implementation: `test_admin_agent_audit_returns_agent_tasks` or the new regression test fails with HTTP 401.

- [x] **Step 3: Implement runtime token lookup**

In `routes/admin.py`, add:

```python
def _get_admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "") or _ADMIN_TOKEN
```

Change `_admin_session_value()`, `_is_valid_admin_session()`, `_verify_admin()`, `admin_page()`, and `admin_login()` to use `_get_admin_token()` instead of reading `_ADMIN_TOKEN` directly for current auth decisions.

The important behavior:

```python
async def _verify_admin(
    authorization: str = Header(default=""),
    lima_admin_session: str = Cookie(default=""),
) -> None:
    token_expected = _get_admin_token()
    if not token_expected:
        raise HTTPException(
            status_code=503,
            detail="LiMa admin token is not configured.",
        )
    if _is_valid_admin_session(lima_admin_session):
        return
    if authorization != f"Bearer {token_expected}" and authorization != token_expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

For cookie session helpers, compute the HMAC using the runtime token.

- [x] **Step 4: Verify focused and full suites**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_access_guard.py tests\test_admin_agent_audit.py -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m pytest -q --ignore=active_model
```

Expected after implementation:

- focused import-order suite passes;
- full suite has zero failures.

## Task 2: Remove Hardcoded Runtime Secrets And Quarantine Local Debug Scripts

**Priority:** P0

**Files:**
- Modify: `backends.py`
- Modify: `mimo_tts.py`
- Modify: `.gitignore`
- Create: `tests/test_secret_hygiene.py`

- [x] **Step 1: Write the failing secret hygiene test**

Create `tests/test_secret_hygiene.py`:

```python
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

RUNTIME_FILES = [
    ROOT / "backends.py",
    ROOT / "mimo_tts.py",
    ROOT / "server.py",
    ROOT / "http_caller.py",
]


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{4,}['\"]"),
    re.compile(r"(?i)(api_key|apikey|secret|token)\s*=\s*['\"][^'\"]{8,}['\"]"),
]


def test_runtime_files_do_not_contain_hardcoded_secret_literals():
    offenders = []
    for path in RUNTIME_FILES:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(path.name)
                break

    assert offenders == []
```

- [x] **Step 2: Run the failing test**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_secret_hygiene.py -q --ignore=active_model
```

Expected before implementation: failure listing `backends.py` and `mimo_tts.py`.

- [x] **Step 3: Remove runtime fallback keys**

Change `backends.py` MiMo TTS backend keys from literal values to environment reads:

```python
'mimo_tts': {
    'url': 'https://api.xiaomimimo.com/v1/chat/completions',
    'key': os.environ.get('MIMO_TTS_KEY', ''),
    'model': 'mimo-v2.5-tts',
    'fmt': 'openai',
    'timeout': 30,
},
'mimo_tts_v2': {
    'url': 'https://api.xiaomimimo.com/v1/chat/completions',
    'key': os.environ.get('MIMO_TTS_KEY', ''),
    'model': 'mimo-v2-tts',
    'fmt': 'openai',
    'timeout': 30,
},
```

Change `mimo_tts.py`:

```python
API_KEY = os.environ.get("MIMO_TTS_KEY", "")
```

Do not add a fallback secret.

- [x] **Step 4: Quarantine local debug/deploy scripts**

Add root-anchored patterns to `.gitignore` so known local scripts do not get staged accidentally:

```gitignore
/debug_routing*.py
/deploy_r*_test.py
/deploy_test_r*.py
/run_debug*.py
/run_r*_test.py
/run_remote_test.py
/stress*_runner.py
/upload_r*.py
/mimo_tts.py
```

If `mimo_tts.py` is intended to become a real runtime module, do not ignore it; instead keep it tracked and sanitized. Decide by checking `git ls-files mimo_tts.py`. If it is untracked, keep it local-only unless there is a dedicated integration plan.

- [x] **Step 5: Verify secret hygiene**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_secret_hygiene.py -q --ignore=active_model
git status --short
```

Expected:

- secret hygiene test passes;
- no credential files or local debug scripts are staged.

## Task 3: Make Web-Reverse Admission Policy Explicit

**Priority:** P1

**Files:**
- Modify: `backends.py`
- Modify: `router_v3.py`
- Modify: `docs/PERSONAL_CODING_ASSISTANT_PLAN.md`
- Modify: `docs/WEB_REVERSE_MODEL_EVAL.md`
- Test: `test_routing_engine.py`

- [x] **Step 1: Add policy assertions**

Add a test to `test_routing_engine.py`:

```python
def test_web_reverse_default_routes_have_explicit_admission_policy():
    import router_v3
    from backends import BACKENDS

    selected = set(router_v3.select_backends("code", {}))
    web_reverse = {
        name for name, cfg in BACKENDS.items()
        if "localhost:450" in cfg.get("url", "") or name.endswith("_web")
    }
    routed = selected.intersection(web_reverse)

    assert routed
    for name in routed:
        cfg = BACKENDS[name]
        assert cfg.get("admission") in {
            "code_medium_candidate",
            "code_floor_candidate",
        }
        assert cfg.get("private_code_allowed") is True
```

- [x] **Step 2: Run the failing policy test**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py::test_web_reverse_default_routes_have_explicit_admission_policy -q --ignore=active_model
```

Expected before implementation: failure because policy fields are missing.

- [x] **Step 3: Add explicit admission metadata**

In `backends.py`, add metadata to any web-reverse backend present in default coding/chat pools:

```python
'longcat_web': {
    'url': 'http://localhost:4506/v1/chat/completions',
    'key': 'local',
    'model': 'longcat-web',
    'fmt': 'openai',
    'timeout': 60,
    'force_stream_param': True,
    'admission': 'code_floor_candidate',
    'private_code_allowed': True,
},
```

Use the evidence-backed values from `docs/WEB_REVERSE_MODEL_EVAL.md`.

Do not mark MiMo web private-code allowed until its cookie/auth blocker is resolved and a fresh three-case eval passes.

- [x] **Step 4: Reconcile documentation**

Change `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` from the blanket rule:

```text
New web AI candidates start in sandbox only.
```

to the explicit policy:

```text
New web AI candidates start in sandbox only. A web-reverse backend may enter default IDE/coding pools only after synthetic three-case eval, explicit `admission` metadata, and an explicit `private_code_allowed` decision in `backends.py`.
```

- [x] **Step 5: Verify route policy**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py tests\test_web_reverse_eval.py -q --ignore=active_model
```

Expected: route policy tests and web-reverse eval tests pass.

## Task 4: Consolidate Retrieval Injection Into One Function

**Priority:** P1

**Files:**
- Modify: `routing_engine.py`
- Test: `tests/test_lightrag.py`
- Test: `test_routing_engine.py`

- [x] **Step 1: Add a regression test for one retrieval trace path**

Add to `test_routing_engine.py`:

```python
def test_route_uses_shared_retrieval_injection(monkeypatch):
    calls = {"count": 0}

    def fake_inject(messages):
        calls["count"] += 1
        return [{"role": "system", "content": "[retrieval]"}] + list(messages), "[retrieval]"

    monkeypatch.setattr(routing_engine, "inject_retrieval_context", fake_inject)
    monkeypatch.setattr(routing_engine, "classify_scenario", lambda *a, **k: "chat")
    monkeypatch.setattr(routing_engine.router_v3, "select_backends", lambda *a, **k: ["unit_backend"])
    monkeypatch.setattr(routing_engine.health_tracker, "get_health_map", lambda: {})

    def call_fn(backend, messages, max_tokens):
        assert messages[0]["content"] == "[retrieval]"
        return "ok"

    result = routing_engine.route(
        "hello",
        [{"role": "user", "content": "hello"}],
        call_fn=call_fn,
    )

    assert result.answer == "ok"
    assert calls["count"] == 1
```

- [x] **Step 2: Run the failing/guard test**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py::test_route_uses_shared_retrieval_injection -q --ignore=active_model
```

Expected before implementation: it may fail or show duplicate behavior because `route()` currently has its own inline retrieval logic.

- [x] **Step 3: Refactor `routing_engine.route()`**

Remove the inline entity extraction / graph retrieval / reranking block from `route()` and call:

```python
messages, retrieval_text = inject_retrieval_context(messages)
```

Keep complexity assessment and downstream routing behavior unchanged.

- [x] **Step 4: Verify retrieval behavior**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lightrag.py test_routing_engine.py tests\test_mcp_tools.py -q --ignore=active_model
```

Expected: retrieval, route, and MCP trace tests pass.

## Task 5: Extract Admin Auth And Agent Audit From `routes/admin.py`

**Priority:** P1

**Files:**
- Create: `routes/admin_auth.py`
- Create: `routes/admin_agent_audit.py`
- Modify: `routes/admin.py`
- Test: `tests/test_access_guard.py`
- Test: `tests/test_admin_agent_audit.py`

- [x] **Step 1: Move admin auth helpers**

Create `routes/admin_auth.py`:

```python
"""Admin authentication helpers."""

import hashlib
import hmac
import os
import secrets

from fastapi import Cookie, Header, HTTPException


SESSION_COOKIE = "lima_admin_session"
_ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "")


def get_admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "") or _ADMIN_TOKEN


def admin_session_value() -> str:
    token = get_admin_token()
    return hmac.new(
        token.encode("utf-8"),
        b"lima-admin-session",
        hashlib.sha256,
    ).hexdigest()


def is_valid_admin_session(value: str) -> bool:
    token = get_admin_token()
    return bool(token and value and secrets.compare_digest(value, admin_session_value()))


async def verify_admin(
    authorization: str = Header(default=""),
    lima_admin_session: str = Cookie(default=""),
) -> None:
    token_expected = get_admin_token()
    if not token_expected:
        raise HTTPException(
            status_code=503,
            detail="LiMa admin token is not configured.",
        )
    if is_valid_admin_session(lima_admin_session):
        return
    if authorization != f"Bearer {token_expected}" and authorization != token_expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

- [x] **Step 2: Move agent audit route**

Create `routes/admin_agent_audit.py`:

```python
"""Admin Agent Task audit routes."""

from fastapi import APIRouter, Depends

from routes.admin_auth import verify_admin

router = APIRouter(prefix="/admin")


@router.get("/api/agent-audit", dependencies=[Depends(verify_admin)])
async def admin_agent_audit(limit: int = 20):
    from routes.agent_tasks import _store, _task_audit_item

    safe_limit = max(1, min(int(limit), 100))
    tasks = list(_store.values())
    tasks.sort(
        key=lambda t: t.get("updated_at", t.get("created_at", 0)),
        reverse=True,
    )
    items = [_task_audit_item(task) for task in tasks[:safe_limit]]
    return {"tasks": items, "count": len(items)}
```

- [x] **Step 3: Rewire `routes/admin.py`**

Import from `routes.admin_auth`:

```python
from routes.admin_auth import (
    SESSION_COOKIE,
    admin_session_value,
    get_admin_token,
    is_valid_admin_session,
    verify_admin,
)
```

Replace dependencies from `_verify_admin` to `verify_admin`.

Remove the inline `/api/agent-audit` function from `routes/admin.py`.

- [x] **Step 4: Include the new router in `server.py`**

After including `admin_router`, include:

```python
from routes.admin_agent_audit import router as admin_agent_audit_router
app.include_router(admin_agent_audit_router)
```

- [x] **Step 5: Verify admin route split**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m py_compile routes\admin.py routes\admin_auth.py routes\admin_agent_audit.py server.py
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_access_guard.py tests\test_admin_agent_audit.py -q --ignore=active_model
```

Expected: compile passes and admin tests pass.

## Task 6: Create A Server Context Stage Module

**Priority:** P2

**Files:**
- Create: `server_context.py`
- Modify: `server.py`
- Test: `tests/test_prompt_memory_recall.py`
- Test: `tests/test_context_pipeline.py`

- [x] **Step 1: Extract a typed context result**

Create `server_context.py`:

```python
"""Server request context staging."""

from dataclasses import dataclass

from response_builder import messages_to_dicts


@dataclass
class ServerPromptContext:
    request_messages: list[dict]
    prompt_context_messages: list[dict]
    system_prompt: str
    memory_recall_meta: dict
    memory_session_id: str


def messages_with_system_context(messages: list[dict], system_prompt: str) -> list[dict]:
    prompt = (system_prompt or "").strip()
    base_messages = [m for m in (messages or []) if m.get("role") != "system"]
    if not prompt:
        return base_messages
    return [{"role": "system", "content": prompt}] + base_messages
```

Move the current `_messages_with_system_context()` logic out of `server.py`.

- [x] **Step 2: Move prompt recall staging**

Add:

```python
def build_prompt_context(
    req,
    *,
    system_prompt: str = "",
    request_headers: dict | None = None,
    client_ip: str = "",
    ide_source: str = "",
    trace=None,
) -> ServerPromptContext:
    request_messages = messages_to_dicts(req.messages)
    memory_recall_meta = {"checked": False, "applied": False, "prompt_chars_added": 0}
    memory_session_id = ""

    try:
        from session_memory.prompt_recall import apply_prompt_memory_recall

        recall = apply_prompt_memory_recall(
            request_messages,
            system_prompt=system_prompt or "",
            headers=request_headers,
            client_ip=client_ip,
            ide_source=ide_source,
            trace=trace,
        )
        system_prompt = recall.system_prompt
        memory_recall_meta = recall.meta()
        memory_session_id = recall.session_id
    except ImportError:
        pass

    return ServerPromptContext(
        request_messages=request_messages,
        prompt_context_messages=messages_with_system_context(request_messages, system_prompt),
        system_prompt=system_prompt,
        memory_recall_meta=memory_recall_meta,
        memory_session_id=memory_session_id,
    )
```

- [x] **Step 3: Rewire `_handle_chat()` to use `ServerPromptContext`**

In `server.py`, replace local variables:

- `request_messages`
- `prompt_context_messages`
- `memory_recall_meta`
- `memory_session_id`

with fields from `prompt_ctx`.

- [x] **Step 4: Verify context staging**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_prompt_memory_recall.py tests\test_context_pipeline.py -q --ignore=active_model
```

Expected: all pass.

## Task 7: Clean Warning Signal For Telegram Tests

**Priority:** P2

**Files:**
- Modify: `routes/telegram.py`
- Modify: `tests/test_telegram_bot.py`

- [x] **Step 1: Replace deprecated startup hook**

In `routes/telegram.py`, replace `@router.on_event("startup")` with an explicit startup function that `server.py` calls from lifespan, or move startup wiring into FastAPI app lifespan.

Keep behavior equivalent:

```python
async def start_telegram_webhook() -> None:
    if os.environ.get("TELEGRAM_ENABLED", "0") != "1":
        return
    await set_webhook_if_configured()
```

- [x] **Step 2: Fix unawaited coroutine tests**

In `tests/test_telegram_bot.py`, ensure mocked async functions use `AsyncMock` and any coroutine-returning helper is awaited through `asyncio.run()` or pytest async support.

Example pattern:

```python
from unittest.mock import AsyncMock

monkeypatch.setattr(telegram_bot, "send_alert", AsyncMock())
```

- [x] **Step 3: Run warning-focused tests**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_telegram_bot.py -q --ignore=active_model -W error::RuntimeWarning
```

Expected: no RuntimeWarning failures.

## Task 8: Final Integration Gate

**Priority:** P0 for merging any of the tasks above.

**Files:**
- Modify: `STATUS.md`
- Modify: `docs/LIMA_MEMORY.md`
- Modify: `progress.md`

- [x] **Step 1: Compile runtime files**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m compileall -q server.py routing_engine.py router_v3.py http_caller.py backends.py response_cleaner.py context_pipeline session_memory routes tool_gateway scripts tests
```

Expected: exit code 0.

- [x] **Step 2: Run full local suite**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q --ignore=active_model
```

Expected: zero failures. Skips are acceptable only for intentionally skipped live-provider tests.

- [x] **Step 3: Run whitespace and status checks**

Run:

```powershell
git diff --check
git status --short
```

Expected:

- no whitespace errors;
- only intended files are modified;
- no `.claude/`, local reference repos, DBs, password scripts, or credential files are staged.

- [x] **Step 4: Update status docs**

Append a short closure note to `progress.md`:

```markdown
## 2026-05-23 Global Code Quality Hardening

- Fixed admin auth import-order test failure.
- Removed hardcoded runtime secret literals from active runtime files.
- Made web-reverse route admission explicit.
- Consolidated retrieval injection path.
- Verified with compileall and full pytest.
```

Update `STATUS.md` only after full pytest is green.

## Execution Order

1. Task 1: restore deterministic tests.
2. Task 2: remove hardcoded runtime secrets and quarantine local scripts.
3. Task 3: reconcile web-reverse route policy.
4. Task 4: consolidate retrieval injection.
5. Task 5: split admin auth/audit modules.
6. Task 6: extract server prompt-context staging.
7. Task 7: clean warning signal.
8. Task 8: final integration gate.

Do not deploy these changes to VPS until Task 8 passes locally and a separate deployment plan is written.
