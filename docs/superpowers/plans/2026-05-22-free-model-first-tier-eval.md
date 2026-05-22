# Free Model First-Tier Evaluation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Determine whether SCNet and Kimi-family free models should be promoted into LiMa's first-tier coding route.

**Architecture:** Run production-like evaluation from the VPS against the actual `/opt/lima-router` backend configuration. Promote only models that are reachable, pass coding fixtures, and have acceptable latency. Keep unreachable or slow models registered but outside first-tier routing.

**Tech Stack:** Python 3.10, existing `http_caller.py`, existing coding fixture semantics, VPS smoke/eval, pytest.

---

## First-Tier Criteria

A model can enter first-tier coding route only if it satisfies all of these:

- Production reachable from VPS without requiring an inactive local proxy.
- Passes at least 3/3 coding fixtures or has clear evidence that failures are evaluator artifacts.
- Average fixture latency is acceptable for IDE use. Target: under 6000ms; over 10000ms is deep fallback only.
- Does not fail with invalid JSON, empty response, connection refused, or repeated timeouts.

## Candidate Set

SCNet candidates:

- `scnet_ds_flash`
- `scnet_ds_pro`
- `scnet_qwen235b`
- `scnet_qwen30b`
- `scnet_minimax`
- `scnet_large_ds_flash`
- `scnet_large_ds_pro`

Kimi candidates:

- `cf_kimi_k26`
- `stock_kimi_k2`
- `kimi`
- `kimi_thinking`
- `kimi_search`

## Tasks

### Task 1: Run VPS Fixture Eval

**Files:**
- Remote read: `/opt/lima-router/http_caller.py`
- Remote read: `/opt/lima-router/backends.py`
- Local update after run: `docs/FREE_MODEL_ROUTING_STATUS.md`
- Local update after run: `docs/LIMA_MEMORY.md`

- [x] **Step 1: Run three coding fixtures from VPS**

Run a remote Python script through SSH that imports `/opt/lima-router/http_caller.py` and calls each candidate with:

- `code_review`
- `json_tool_output`
- `python_bugfix`

- [x] **Step 2: Collect raw JSON results**

Save backend, case id, score, pass/fail, latency, notes, and response preview.

### Task 2: Decide First-Tier Eligibility

**Files:**
- Modify: `docs/FREE_MODEL_ROUTING_STATUS.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [x] **Step 1: Apply first-tier criteria**

Classify each candidate as:

- `first_tier_candidate`
- `active_fallback`
- `deep_fallback`
- `inactive_until_proxy_fixed`
- `inactive_due_to_failure`

- [x] **Step 2: Decide routing change**

Only modify `code_orchestrator.py` and `router_v3.py` if at least one candidate meets first-tier criteria.

### Task 3: Verify And Deploy If Needed

**Files:**
- Optional modify: `code_orchestrator.py`
- Optional modify: `router_v3.py`
- Test: `test_routing_engine.py`

- [x] **Step 1: Run local verification**

Run:

```powershell
python -m py_compile lima_context.py code_orchestrator.py server.py routing_engine.py router_v3.py coding_eval.py
python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py
```

- [x] **Step 2: Deploy only if runtime routing changes**

If code changes are made, backup changed runtime files on VPS, upload, compile, restart, and smoke `/health`.

## Closure

- [ ] Update `docs/FREE_MODEL_ROUTING_STATUS.md` with the fixture table.
- [x] Update `docs/FREE_MODEL_ROUTING_STATUS.md` with the fixture table.
- [x] Update `docs/LIMA_MEMORY.md` with first-tier decision.
- [x] Update `task_plan.md`, `findings.md`, and `progress.md`.
- [x] Report whether SCNet/Kimi should enter first tier.

## Eval Decision

- Promote to first tier: `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`.
- Keep fallback only: `cf_kimi_k26`.
- Keep inactive until proxy/format fixes: `kimi`, `kimi_thinking`, `kimi_search`, `stock_kimi_k2`, `scnet_large_ds_flash`, `scnet_large_ds_pro`, `scnet_minimax`.

## Deployment Evidence

- Local verification: `71 passed in 0.59s`.
- VPS backup: `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- VPS `/health`: 200.
- Route-order smoke: `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, `github_gpt4o`.
- Public coding smoke: 200 in 3347ms.
