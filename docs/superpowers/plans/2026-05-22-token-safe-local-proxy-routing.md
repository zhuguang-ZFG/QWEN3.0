# Token-Safe Local Proxy Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent token leakage from refresh tooling and prevent Windows-only local proxy backends from being selected on runtimes where their localhost ports are unavailable.

**Architecture:** Add a small runtime topology helper in LiMa and use it from routing/code execution paths. Local-only backends are active only when explicitly enabled or when their local port is reachable. Add a reusable JavaScript redactor for `D:\ollama_server` refresh scripts and make refresh endpoints return status metadata instead of raw tokens.

**Tech Stack:** Python 3.10, pytest, existing LiMa routing modules, Node.js local proxy scripts under `D:\ollama_server`.

---

## File Structure

- Create `runtime_topology.py`: local-only backend names, localhost port detection, and backend availability predicate.
- Modify `router_v3.py`: filter selected backend pools through topology guard.
- Modify `code_orchestrator.py`: filter coding tower backend pools before trying them.
- Modify `test_routing_engine.py`: assert local-only backends are excluded by default and included when explicitly enabled.
- Modify `D:\ollama_server\secret_redactor.js`: reusable redaction helper for token-like strings.
- Modify `D:\ollama_server\kimi_refresh.js`: remove hardcoded Cloudflare token and redact captured token logs.
- Modify `D:\ollama_server\refresh_theoldllm_token.js`: redact request/body/localStorage/token logs and read Cloudflare token only from environment.
- Modify `D:\ollama_server\token_refresh_server.js`: never return raw tokens from `/refresh`.
- Modify `D:\ollama_server\oldllm_proxy.js`: redact refresh logs.
- Update `STATUS.md`, `docs/LIMA_MEMORY.md`, `findings.md`, and `task_plan.md`.

## Guardrails

- Do not print real tokens, cookies, Authorization headers, or token file values.
- Do not commit files from `D:\ollama_server`; they are local runtime assets, not repo source.
- Keep direct SCNet first-tier order unchanged.
- Local-only backends must not be selected on VPS unless an explicit tunnel URL or enable flag is present.
- Do not run refresh scripts until redaction is implemented.

### Task 1: Runtime Topology Guard

**Files:**
- Create: `runtime_topology.py`
- Modify: `router_v3.py`
- Modify: `code_orchestrator.py`
- Modify: `test_routing_engine.py`

- [ ] **Step 1: Add failing route tests**

Add tests that call:

```python
with patch.dict(os.environ, {}, clear=False):
    os.environ.pop("LIMA_ENABLE_LOCAL_PROXIES", None)
    selected = router_v3.select_backends("code", {})
    assert "scnet_large_ds_flash" not in selected
```

Then test explicit enable:

```python
with patch.dict(os.environ, {"LIMA_ENABLE_LOCAL_PROXIES": "1"}):
    assert runtime_topology.backend_available("scnet_large_ds_flash")
```

- [ ] **Step 2: Implement `runtime_topology.py`**

Expose:

```python
LOCAL_ONLY_BACKENDS = {
    "ddg_gpt4o_mini", "ddg_gpt5_mini", "ddg_claude_haiku_45",
    "ddg_llama4", "ddg_mistral", "ddg_tinfoil_gptoss_120b",
    "kimi", "kimi_thinking", "kimi_search",
    "scnet_large_ds_flash", "scnet_large_ds_pro",
    "local_coder14b", "local_reasoning", "local_general",
    "local_fast", "local_chat", "local_qwen3", "local_phi4", "local_mistral",
}

def backend_available(name: str) -> bool:
    ...

def filter_backends(names: list[str]) -> list[str]:
    ...
```

Availability is true when:

- backend is not local-only; or
- `LIMA_ENABLE_LOCAL_PROXIES` is truthy; or
- the backend has a tunnel URL env override, such as `DDG_TUNNEL_URL`, `OLLAMA_TUNNEL_URL`; or
- its expected local port accepts a short TCP connection.

- [ ] **Step 3: Wire topology filter**

Use `runtime_topology.filter_backends` in:

- `router_v3.select_backends`
- `code_orchestrator._try_backends_ranked`

### Task 2: Token-Safe Refresh Scripts

**Files:**
- Create: `D:\ollama_server\secret_redactor.js`
- Modify: `D:\ollama_server\kimi_refresh.js`
- Modify: `D:\ollama_server\refresh_theoldllm_token.js`
- Modify: `D:\ollama_server\token_refresh_server.js`
- Modify: `D:\ollama_server\oldllm_proxy.js`

- [ ] **Step 1: Add redactor helper**

Create:

```javascript
function redactSecret(value) {
  if (!value) return value;
  return String(value)
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]{12,}/g, 'Bearer [REDACTED]')
    .replace(/cfut_[A-Za-z0-9._~+/=-]+/g, 'cfut_[REDACTED]')
    .replace(/mpf[A-Za-z0-9._~+/=-]{8,}/g, 'mpf[REDACTED]')
    .replace(/on_tenant_[A-Za-z0-9._~+/=-]+/g, 'on_tenant_[REDACTED]');
}

function safeLog(...args) {
  console.log(...args.map(redactSecret));
}

module.exports = { redactSecret, safeLog };
```

- [ ] **Step 2: Remove hardcoded Cloudflare tokens**

In Kimi and TheOldLLM refresh scripts, read Cloudflare token from environment variables only:

```javascript
const CF_TOKEN = process.env.CLOUDFLARE_API_TOKEN || process.env.CF_API_TOKEN;
if (!CF_TOKEN) throw new Error('Set CLOUDFLARE_API_TOKEN or CF_API_TOKEN');
```

- [ ] **Step 3: Redact all token logs**

Replace logs that include token, Authorization, X-Request-Token, post body, localStorage, or errors that may include request headers with `safeLog`.

- [ ] **Step 4: Stop refresh server from returning raw tokens**

`GET /refresh` should return:

```json
{"ok": true, "cached": false, "token_present": true}
```

not the token itself.

### Task 3: Verification

**Files:**
- No new runtime files.

- [ ] **Step 1: Python verification**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m py_compile runtime_topology.py router_v3.py code_orchestrator.py test_routing_engine.py
D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py tests\test_lima_context.py -q --ignore=active_model
```

Expected: all selected tests pass.

- [ ] **Step 2: JavaScript syntax verification**

Run:

```powershell
node --check D:\ollama_server\secret_redactor.js
node --check D:\ollama_server\kimi_refresh.js
node --check D:\ollama_server\refresh_theoldllm_token.js
node --check D:\ollama_server\token_refresh_server.js
node --check D:\ollama_server\oldllm_proxy.js
```

Expected: all syntax checks pass.

- [ ] **Step 3: Redactor behavior check**

Run a small Node command importing `secret_redactor.js` and assert test values are redacted.

- [ ] **Step 4: No refresh execution**

Do not run Kimi/TheOldLLM refresh scripts in this implementation pass. Only syntax and redaction behavior are verified.

### Task 3B: Production Short-Answer Fallback Hotfix

**Files:**
- Modify: `server.py`
- Modify: `test_routing_engine.py`

During VPS verification, public `/v1/chat/completions` returned `fallback_exhausted` for `Return exactly: topology-ok` even though direct backend calls and `routing_engine.route` succeeded. Root cause: the server-level quality gate rejected short but explicitly requested exact-output answers (`len(response) < 30` with complexity above `0.3`), then the fallback chain retried another short-answer backend and exhausted.

- [ ] **Step 1: Add regression coverage**

Assert that `_quality_check("topology-ok", 0.5, ..., query="Return exactly: topology-ok")` passes while unrelated short responses to complex prompts still fail.

- [ ] **Step 2: Implement exact-output short-answer handling**

Keep backend-error and `[ERR]` rejection first. Add small helpers that:

- allow short answers only when the prompt explicitly requests exact/direct output, such as `return exactly`, `respond exactly`, `output exactly`, `只返回`, or `只输出`;
- reject non-matching answers when the prompt has a parseable expected answer such as `Return exactly: topology-ok`.

- [ ] **Step 3: Wire query context into quality checks**

Pass the current `query` into non-streaming and fake-stream fallback quality checks so the gate can distinguish intentional short answers from low-quality truncation.

### Task 4: Documentation And Git

**Files:**
- Modify: `STATUS.md`
- Modify: `docs/LIMA_MEMORY.md`
- Modify: `findings.md`
- Modify: `task_plan.md`

- [ ] **Step 1: Record what changed**

Document:

- topology guard behavior
- local script redaction behavior
- refresh scripts were not executed
- local runtime files under `D:\ollama_server` were changed but not committed

- [ ] **Step 2: Commit repo changes**

Commit only repo files. Do not stage unrelated untracked directories.
