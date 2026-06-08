# Telegram Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire and remove Telegram bot/operator support from LiMa Server while preserving the private coding API, Agent Task, GitHub/Gitee webhook ingestion, Device Gateway, and VPS health paths.

**Architecture:** Remove the `/telegram` route and all Telegram-specific runtime modules, tests, deploy/smoke scripts, and active docs. Replace cross-module Telegram notification hooks with local logging or existing internal activity ledgers so non-Telegram flows keep working without optional imports or silent degradation.

**Tech Stack:** FastAPI route registry and lifespan, Python notification hooks, pytest, ruff, pyright, VPS deploy through existing LiMa deploy scripts.

---

## File Structure

- Modify: `routes/route_registry.py` to stop registering `/telegram`.
- Modify: `server_lifespan.py` to stop starting Telegram digest/probe/broadcast loops.
- Modify: `routes/github_webhook.py` and `routes/gitee_webhook.py` so webhook activity is recorded without Telegram notification.
- Modify: `routes/agent_task_service.py` so `needs_review` task results do not import Telegram card delivery.
- Modify: deploy/ops scripts that invoked Telegram notification helpers.
- Delete: root Telegram modules `telegram_*.py` and `telegram_bot.py`.
- Delete: `routes/telegram*.py`.
- Delete: `tests/test_telegram*.py`.
- Delete: Telegram deploy/smoke scripts and Cloudflare worker file.
- Update: `STATUS.md`, `progress.md`, `findings.md`, `docs/LIMA_MEMORY.md`, `docs/DOCUMENTATION_STATUS.md`, `docs/NEXT_MILESTONES.md`, and `task_plan.md`.

## Tasks

### Task 1: Remove Runtime Registration

**Files:**
- Modify: `routes/route_registry.py`
- Modify: `server_lifespan.py`

- [x] Remove the `routes.telegram` import, `app.include_router(telegram_router)`, and `loaded_modules["telegram"]` startup state.
- [x] Remove the lifespan call to `start_telegram_webhook()`.
- [x] Add local route-registry coverage proving `/telegram` is gone and `telegram=false`.

### Task 2: Remove Telegram Notification Coupling

**Files:**
- Modify: `routes/agent_task_service.py`
- Modify: `routes/github_webhook.py`
- Modify: `routes/gitee_webhook.py`
- Modify: `scripts/deploy_common.py`
- Modify or delete: `scripts/notify_ops_telegram.py`, `scripts/ci_notify.py`, `scripts/archive_eval_to_telegram.py`, `scripts/smoke_telegram_outbound.py`

- [x] Replace task-review Telegram card notification with a structured log entry.
- [x] Keep GitHub/Gitee webhook activity recording, but remove Telegram push calls.
- [x] Remove deploy/smoke helpers that depend on Telegram credentials.

### Task 3: Delete Telegram Bot Files

**Files:**
- Delete: `telegram_bot.py`, `telegram_notify.py`, `telegram_async.py`, `telegram_archive.py`, `telegram_b2b.py`, `telegram_digest.py`, `telegram_draft_stream.py`, `telegram_inline.py`, `telegram_operator_tools.py`, `telegram_outbound.py`, `telegram_push_translate.py`
- Delete: `routes/telegram.py`, `routes/telegram_*.py`
- Delete: `tests/test_telegram*.py`
- Delete: `deploy/telegram_cf_worker.js`
- Delete: `scripts/deploy_telegram.sh`, `scripts/notify_ops_telegram.py`, `scripts/archive_eval_to_telegram.py`, `scripts/smoke_telegram_outbound.py`

- [x] Delete Telegram-only files from the repository.
- [x] Run `rg -n "telegram|TELEGRAM|/telegram|telegram_bot|telegram_notify"` and review remaining hits as historical docs, env examples, or comments to update.

### Task 4: Update Tests And Docs

**Files:**
- Modify: tests that expect Telegram module state or Telegram env checks.
- Modify: active status docs listed above.

- [x] Add or update route-registry/health tests proving Telegram is not loaded or registered.
- [x] Remove Telegram-focused test files from the active suite.
- [x] Record retirement evidence and residual risks in active docs.

### Task 5: Validate, Deploy, Commit

**Commands:**

```powershell
.\.venv310\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_agent_task_routes.py tests/test_agent_task_contract.py tests/test_github_webhook.py tests/test_gitee_webhook.py tests/test_ops_metrics.py tests/test_repo_hygiene.py -q
.\.venv310\Scripts\ruff.exe check routes scripts tests --config ruff.toml
.\.venv310\Scripts\pyright.exe routes\route_registry.py server_lifespan.py routes\agent_task_service.py routes\github_webhook.py routes\gitee_webhook.py
git diff --check
```

- [x] Run focused local validation.
- [x] Deploy changed runtime files to VPS with a backup.
- [x] Public smoke `/health`, authenticated `model=code` chat, GitHub/Gitee activity path, and confirm `/telegram/webhook` is no longer available.
- [ ] Stage only Telegram-retirement related files.
- [ ] Commit and push GitHub `origin`; record Gitee mirror status based on configured remotes.
