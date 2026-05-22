# Cloudflare Workers AI Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put already available Cloudflare text/code capacity into LiMa's active coding routes without changing credential handling or production deployment flow.

**Architecture:** Keep Cloudflare as normal OpenAI-compatible backends. Direct account backends keep using `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_TOKEN`; the public Worker wrapper remains a zero-key fallback path. Route only chat-completion-capable models into coding/chat pools; embeddings, image, speech, and other non-chat models require later adapters.

**Tech Stack:** Python 3.10, FastAPI routing modules, existing `BACKENDS` dictionary, existing `router_v3.POOLS`, existing `code_orchestrator.POOLS`, pytest, PowerShell smoke checks.

---

## File Structure

- Modify `backends.py`: add the missing `cfai_mistral` backend that is already exposed by `https://ai.zhuguang.ccwu.cc/v1/models`.
- Modify `router_v3.py`: add verified Worker `cfai_*` and stronger direct `cf_*` code-capable backends to active `code`, `ide`, `chat`, and `chat_fast` pools.
- Modify `code_orchestrator.py`: add Cloudflare code-capable models to the dedicated coding tower while keeping SCNet winners first.
- Modify `test_routing_engine.py`: add focused assertions that Cloudflare code capacity is present without disturbing first-tier SCNet order.
- Create `docs/CLOUDFLARE_MODEL_INVENTORY.md`: record what is used, what is missing, and what requires a separate adapter.
- Update `STATUS.md` and `docs/LIMA_MEMORY.md`: record the current Cloudflare state and next constraints.

## Guardrails

- Do not print or hardcode Cloudflare secrets.
- Do not reorder the first three SCNet winners in coding pools.
- Do not route non-chat models through `chat/completions`.
- Do not deploy to VPS in this step; this is local implementation plus verification.
- Keep changes small and reversible.

### Task 1: Document Cloudflare Inventory

**Files:**
- Create: `docs/CLOUDFLARE_MODEL_INVENTORY.md`

- [ ] **Step 1: Write inventory doc**

Record three buckets:

```markdown
# Cloudflare Model Inventory

## Current Integration

Direct account API backends:
- cf_llama70b
- cf_llama4
- cf_qwen_coder
- cf_mistral
- cf_vision
- cf_kimi_k26
- cf_deepseek_r1
- cf_qwq
- cf_gptoss_120b
- cf_qwen3_30b
- cf_nemotron
- cf_glm47
- cf_gemma4

Worker wrapper backends:
- cfai_llama70b
- cfai_llama4
- cfai_qwen_coder
- cfai_deepseek_r1
- cfai_mistral

## Routing Policy

Text/code chat models may enter `router_v3` and `code_orchestrator` pools.
Non-chat models need separate adapters.
```

- [ ] **Step 2: Verify doc exists**

Run: `Test-Path docs\CLOUDFLARE_MODEL_INVENTORY.md`
Expected: `True`

### Task 2: Add Missing Worker Backend

**Files:**
- Modify: `backends.py`

- [ ] **Step 1: Add `cfai_mistral`**

Insert next to other `cfai_*` entries:

```python
'cfai_mistral': {'url': 'https://ai.zhuguang.ccwu.cc/v1/chat/completions', 'key': 'none', 'model': 'mistral-small-3.1', 'fmt': 'openai', 'timeout': 30},
```

- [ ] **Step 2: Compile backend registry**

Run: `D:\GIT\venv\Scripts\python.exe -m py_compile backends.py`
Expected: exit code 0.

### Task 3: Route Cloudflare Code Capacity

**Files:**
- Modify: `router_v3.py`
- Modify: `code_orchestrator.py`

- [ ] **Step 1: Keep SCNet first**

Do not change these prefixes:

```python
router_v3.POOLS["code"]["strong"][:4] == [
    "scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b", "scnet_ds_pro"
]
code_orchestrator.POOLS["coder"][:4] == [
    "scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b", "scnet_ds_pro"
]
```

- [ ] **Step 2: Add Cloudflare after existing first-tier winners**

Add these models to coding pools after SCNet/GitHub fast winners and before weak floor fallbacks:

```python
[
    "cf_qwen_coder",
    "cfai_qwen_coder",
    "cf_gptoss_120b",
    "cf_deepseek_r1",
    "cf_qwen3_30b",
    "cfai_deepseek_r1",
    "cfai_llama70b",
    "cfai_llama4",
]
```

- [ ] **Step 3: Add Worker fallback capacity to chat pools**

Add `cfai_qwen_coder`, `cfai_deepseek_r1`, `cfai_llama70b`, and `cfai_llama4` to `ide`, `chat`, and `chat_fast` medium/floor-equivalent sections where direct `cf_*` models already exist.

Execution adjustment: `cfai_mistral` stayed registered but was removed from active route pools after the quick coding eval returned HTTP 500.

### Task 4: Add Focused Tests

**Files:**
- Modify: `test_routing_engine.py`

- [ ] **Step 1: Add assertions**

Add a test that verifies:

```python
cloudflare_code = {
    "cf_qwen_coder",
    "cfai_qwen_coder",
    "cf_gptoss_120b",
    "cf_deepseek_r1",
    "cf_qwen3_30b",
    "cfai_deepseek_r1",
}
assert cloudflare_code.issubset(set(router_v3.POOLS["code"]["strong"]))
assert cloudflare_code.issubset(set(code_orchestrator.POOLS["coder"]))
assert "cfai_mistral" in BACKENDS
```

- [ ] **Step 2: Run focused test**

Run: `D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py -q`
Expected: all tests pass.

### Task 5: Verify Live Worker and Update Status

**Files:**
- Modify: `STATUS.md`
- Modify: `docs/LIMA_MEMORY.md`

- [ ] **Step 1: Verify live Worker model list**

Run:

```powershell
Invoke-RestMethod -Uri 'https://ai.zhuguang.ccwu.cc/v1/models' -TimeoutSec 20
```

Expected: includes `qwen2.5-coder-32b` and `mistral-small-3.1`.

- [ ] **Step 2: Verify one live Worker completion**

Run:

```powershell
$body = @{ model='qwen2.5-coder-32b'; messages=@(@{role='user'; content='Return exactly: cfai-ok'}); max_tokens=20; temperature=0 } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri 'https://ai.zhuguang.ccwu.cc/v1/chat/completions' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 30
```

Expected: response content is `cfai-ok`.

- [ ] **Step 3: Update docs**

Record that the public Worker path is verified and that direct account API smoke is blocked in the current shell because Cloudflare env vars are not set.

### Task 6: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Compile touched Python files**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m py_compile backends.py router_v3.py code_orchestrator.py test_routing_engine.py
```

Expected: exit code 0.

- [ ] **Step 2: Run focused core tests**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py tests\test_coding_eval.py tests\test_lima_context.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Inspect diff**

Run: `git diff -- backends.py router_v3.py code_orchestrator.py test_routing_engine.py docs/CLOUDFLARE_MODEL_INVENTORY.md STATUS.md docs/LIMA_MEMORY.md`
Expected: only Cloudflare routing, inventory, and status updates.
