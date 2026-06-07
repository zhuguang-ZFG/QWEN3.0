# Execution Surface Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close unauthenticated execution-capable routes, prevent unsafe web fetches, and keep OpenCode text-tool deployment complete.

**Architecture:** Reuse LiMa's existing `require_private_api_key` dependency for public HTTP auth. Keep fleet worker compatibility by sending a Bearer token from environment, and keep deployment fixes to explicit file lists.

**Tech Stack:** FastAPI dependencies, Python stdlib URL/IP validation, httpx, pytest, ruff.

---

### Task 1: Protect Execution-Capable Routers

**Files:**
- Modify: `routes/fleet_api.py`
- Modify: `routes/agent_execute.py`
- Modify: `fleet/agent.py`
- Test: `tests/test_fleet_routes_auth.py`
- Test: `tests/test_agent_execute_auth.py`

- [ ] Add regression tests proving `/fleet/submit`, `/fleet/poll/{node_id}`, `/fleet/complete`, `/agent/execute`, and `/agent/execute/status` require auth.
- [ ] Add `Depends(require_private_api_key)` at router level for fleet and agent execute APIs.
- [ ] Add fleet worker Bearer token support from `LIMA_API_KEY`, `LIMA_FLEET_API_KEY`, or `LIMA_AGENT_API_KEY`.
- [ ] Run the new auth tests and existing fleet/safe execution tests.

### Task 2: Harden Web Tools

**Files:**
- Modify: `lima_fc_tools/web_tools.py`
- Test: `tests/test_lima_fc_web_tools_security.py`

- [ ] Add URL validation that only permits `http` and `https`.
- [ ] Block localhost, loopback, link-local, multicast, unspecified, and private IP targets.
- [ ] Preserve existing fetch behavior for normal public URLs while using TLS verification.
- [ ] Run the new web tool security tests.

### Task 3: Fix OpenCode Deployment Completeness

**Files:**
- Modify: `deploy_opencode.py`
- Modify: `scripts/deploy_vps_bundle.py`
- Modify: `scripts/deploy_unified.py`
- Existing untracked dependency: `opencode_text_tool_payload.py`

- [ ] Add `opencode_text_tool_payload.py` to explicit OpenCode/bundle deploy file lists.
- [ ] Add OpenCode direct-stream files to relevant deploy lists where missing.
- [ ] Make `scripts/deploy_unified.py` expand `CORE_DIRS` when deploying all/core slices.
- [ ] Run focused OpenCode tests and deploy script dry-run if practical.

### Task 4: Verify

**Files:**
- All touched files.

- [ ] Run focused pytest targets.
- [ ] Run ruff on touched files.
- [ ] Report remaining risk and any tests not run.
