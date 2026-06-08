# LiMa Code Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the LiMa Code / `deepcode-cli` submodule integration from the LiMa main repository while keeping the generic LiMa Server, Agent Task, routing, Telegram, and Device Gateway surfaces healthy.

**Architecture:** Remove the tracked submodule and all active references that require `deepcode-cli` to exist. Convert reusable server-side worker/task language from LiMa Code-specific wording to generic Agent Worker wording, and delete LiMa Code-only launchers and smoke scripts.

**Tech Stack:** Git submodules, FastAPI routes, Python scripts/tests, project status docs, VPS deployment through the existing LiMa deploy scripts.

---

## File Structure

- Delete: `deepcode-cli` gitlink and `.gitmodules` entry.
- Delete: tracked `.lima-code` client config examples from the main repo.
- Delete: `docs/LIMACODE_MANAGEMENT.md`.
- Delete: local LiMa Code launchers `start_lima.cmd`, `start_lima.ps1`, `start_lima.vbs`, `start_lima_test.ps1`.
- Delete: LiMa Code-only smoke/verification scripts that import or execute `deepcode-cli`.
- Modify: Agent Task server routes and tests to say Agent Worker instead of LiMa Code worker.
- Modify: active status docs to record the retirement and remove `deepcode-cli` from active component tables.
- Keep: historical closeout logs as evidence history, with a new retirement entry superseding the old direction.

## Tasks

### Task 1: Remove Submodule Metadata

**Files:**
- Modify: `.gitmodules`
- Delete: `deepcode-cli`
- Delete: `.lima-code/mcp-playwright.example.json`
- Delete: `.lima-code/skill-rules.json`

- [x] Remove the `deepcode-cli` submodule stanza from `.gitmodules`.
- [x] Remove tracked `.lima-code` client config examples from the main repo.
- [ ] Remove the `deepcode-cli` gitlink from the main repository index.
- [ ] Verify `git ls-files --stage deepcode-cli` returns no entry.

### Task 2: Remove LiMa Code Active Scripts

**Files:**
- Delete: `start_lima.cmd`
- Delete: `start_lima.ps1`
- Delete: `start_lima.vbs`
- Delete: `start_lima_test.ps1`
- Delete: `scripts/stress_headless.py`
- Delete: `scripts/stress_test_lima.py`
- Delete: `scripts/verify_lcw1_worker_context.ts`
- Delete: `scripts/verify_lcw2_hooks_e2e.ts`
- Delete: `scripts/verify_tg_gh2_limacode_telegram.ts`

- [x] Delete launchers and smoke scripts that require `D:\GIT\deepcode-cli`.
- [x] Replace or remove tests that mention those deleted scripts.

### Task 3: De-LiMa-Code Server Text

**Files:**
- Modify: `routes/agent_tasks.py`
- Modify: `routes/agent_task_service.py`
- Modify: `routes/chat_handler_dispatch.py`
- Modify: `routes/ops_metrics.py`
- Modify: `telegram_b2b.py`
- Modify: `telegram_notify.py`
- Modify: `observability/cli_telemetry.py`
- Modify: `session_memory/learning_loop.py`
- Modify: `search_gateway/codesearch_adapter.py`
- Modify: `tool_gateway/registry.py`
- Modify: `routes/telegram_cards.py`

- [x] Change user-visible strings and comments from LiMa Code-specific wording to generic Agent Worker / developer-tool wording.
- [x] Remove `lima-code` as a first-class model alias while keeping `code` routing.
- [x] Preserve public/private API authentication behavior.

### Task 4: Update Tests And Active Docs

**Files:**
- Modify: tests that use `D:/GIT/deepcode-cli` fixtures.
- Modify: `.gitignore`, `.coveragerc`, `ruff.toml`, `pyrightconfig.json`, `.gitleaks.toml`, `.env.example`.
- Modify: `STATUS.md`, `docs/LIMA_MEMORY.md`, `docs/DOCUMENTATION_STATUS.md`, `docs/NEXT_MILESTONES.md`, `docs/WORKSPACE_HYGIENE.md`, `task_plan.md`, `progress.md`, `findings.md`.

- [x] Update tests to use `D:/GIT` or a generic worker repository fixture.
- [x] Remove active configuration exclusions for `deepcode-cli`.
- [ ] Add retirement closeout evidence to active status docs.

### Task 5: Validate, Deploy, And Close

**Commands:**

```powershell
python -m pytest tests/test_agent_task_routes.py tests/test_agent_task_contract.py tests/test_lima_smoke_task_script.py tests/test_repo_hygiene.py tests/test_telegram_b2b.py tests/test_ops_metrics.py tests/test_admin_agent_audit.py -q
ruff check . --config ruff.toml
pyright
git diff --check
```

- [ ] Run focused validation first.
- [ ] Run broader local validation appropriate to the changed production files.
- [ ] Deploy changed server files to VPS, restart `lima-router`, and verify `/health`.
- [ ] Record local and VPS evidence in `progress.md` and `findings.md`.
- [ ] Stage only retirement-related files, commit, and push to `origin` and `gitee`.
