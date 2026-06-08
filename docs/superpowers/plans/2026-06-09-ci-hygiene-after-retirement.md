# CI Hygiene After Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the post-retirement local gate noise and public edge drift that block future LiMa Server optimization work.

**Architecture:** Keep the backend registry as the source of truth by migrating still-referenced backend definitions into the split `backends_registry/` package. Keep CI lint deterministic by making the ruff wrapper inspect only git-tracked Python files, not local scratch or unrelated operator experiments.

**Tech Stack:** Python backend registry modules, pytest, ruff, Git tracked-file discovery.

---

## File Structure

- Modify: `backends_registry/misc.py` for local and direct fallback backend definitions still referenced by `router_v3.DIRECT_BACKENDS`.
- Modify: `backends_registry/free_web.py` for DuckAI fallback backend definitions still referenced by routing pools.
- Modify: `backends_constants.py` for phantom OpenRouter capability/proxy constants and IDE fingerprint ownership.
- Modify: `backends_registry/coding_pool.py` for missing coding provider entries referenced by `code_orchestrator_context.POOLS`.
- Modify: `scripts/run_ruff_check.py` to lint only tracked Python files.
- Modify: `tests/test_ci_gates.py` to cover the tracked-file filtering behavior.
- Modify: `infra/vps/nginx/api.donglicao.com.conf` and `infra/vps/nginx/chat.donglicao.com.conf` to keep retired `/telegram/*` paths unavailable at the edge.
- Update: `progress.md`, `findings.md`, and `STATUS.md` with evidence.

## Tasks

### Task 1: Restore Registry Completeness

**Files:**
- Modify: `backends_registry/misc.py`
- Modify: `backends_registry/free_web.py`
- Modify: `backends_registry/openrouter.py`
- Modify: `backends_registry/coding_pool.py`

- [x] Reproduce `tests/test_backend_registry.py` failures for missing pool/capability entries.
- [x] Add the missing backend definitions to the split registry package without changing route order.
- [x] Remove phantom OpenRouter capability/proxy constants that have no registry definitions.
- [x] Move IDE fingerprints into `backends_constants.py` so `router_v3` and `backends` share one source without circular imports.
- [x] Run focused backend registry and route-registry pytest.

### Task 2: Make Ruff Gate Ignore Scratch Files

**Files:**
- Modify: `scripts/run_ruff_check.py`
- Modify: `tests/test_ci_gates.py`

- [x] Reproduce `scripts/run_ruff_check.py` scanning untracked scratch files.
- [x] Change the wrapper to call `git ls-files` and pass only tracked `.py` / `.pyi` files to ruff.
- [x] Add a small unit-level test proving non-Python and untracked-looking paths are filtered out before ruff invocation.
- [x] Run `pytest tests/test_ci_gates.py -q` and `python scripts/run_ruff_check.py`.

### Task 3: Public Telegram Edge Guard

**Files:**
- Modify: `infra/vps/nginx/api.donglicao.com.conf`
- Modify: `infra/vps/nginx/chat.donglicao.com.conf`
- Modify: `docs/ONLINE_DISTRIBUTIONS.md`
- Modify: `docs/LIMA_MEMORY.md`

- [x] Reproduce public `POST https://api.donglicao.com/telegram/webhook` returning JSON-RPC HTTP `200` through the compatibility backend.
- [x] Back up live nginx configs on VPS before editing.
- [x] Add edge-level `location ^~ /telegram/ { return 404; }` on both public domains.
- [x] Run `nginx -t`, reload nginx, and verify public POST `/telegram/webhook` returns HTTP `404` from VPS and local public exits.

### Task 4: Focused Validation And Closeout

**Files:**
- Modify: `progress.md`
- Modify: `findings.md`
- Modify: `STATUS.md`

- [x] Run focused pytest for registry, CI gate, auto-indexer, and retirement guard tests.
- [x] Run ruff on touched Python files.
- [x] Run CI-style pytest with documented long/external ignores.
- [x] Run `git diff --check` and staged secret scan before commit.
- [ ] Stage only CI-hygiene slice files.
- [ ] Commit, push GitHub `origin`, and record Gitee remote status.
