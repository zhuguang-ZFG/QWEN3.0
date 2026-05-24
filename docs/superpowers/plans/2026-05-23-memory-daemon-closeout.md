# Memory Daemon Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LiMa Session Memory a verifiable always-on background daemon rather than only a request-path compaction hook.

**Architecture:** Keep the existing `session_memory/daemon.py` and `server.py` lifespan integration. Add daemon lifecycle state, dynamic environment config, a single-cycle runner for tests/ops, and focused tests proving inbox ingestion plus consolidation can run outside `/v1/chat/completions`.

**Tech Stack:** Python stdlib asyncio, SQLite-backed `session_memory.store`, pytest.

---

## Scope

- Do not add LLM-based expensive consolidation in this slice.
- Do not ingest secrets; keep existing redaction gate.
- Do not change prompt-time recall behavior.
- Do not deploy to VPS in this local closeout.

## Tasks

### Task 1: Lifecycle And Status

**Files:**
- Modify: `session_memory/daemon.py`
- Test: `tests/test_typed_memory.py`

- [x] Add a daemon task handle so `start_daemon()` is idempotent and `stop_daemon()` cancels the background task.
- [x] Add `daemon_status()` with `running`, `task_alive`, `inbox_dir`, `interval_seconds`, `cycles`, `last_cycle_at`, `last_ingested`, `last_consolidated`, and `last_error`.
- [x] Make inbox path and interval read current environment values at runtime so tests and deployments can override them safely.

### Task 2: Run Once

**Files:**
- Modify: `session_memory/daemon.py`
- Test: `tests/test_typed_memory.py`

- [x] Add `run_once()` that ingests inbox files and consolidates sessions once without requiring a live FastAPI server.
- [x] Return exact counts for ingested facts and consolidated sessions.
- [x] Keep processed inbox files archived under `.processed/`.

### Task 3: CLI Smoke

**Files:**
- Create: `scripts/memory_daemon_ctl.py`
- Test: `tests/test_memory_daemon_ctl.py`

- [x] Add `status` and `run-once` commands.
- [x] Print JSON only, with no secrets.
- [x] Let operators run a safe local smoke before VPS deployment.

### Task 4: Documentation

**Files:**
- Modify: `STATUS.md`
- Modify: `docs/LIMA_MEMORY.md`
- Modify: `progress.md`

- [x] Replace outdated "not always-on" notes with the current server-lifespan daemon status.
- [x] Record remaining boundary: prompt-time recall is still separate from this daemon closeout.

## Verification

```powershell
D:\GIT\venv\Scripts\python.exe -m py_compile session_memory\daemon.py scripts\memory_daemon_ctl.py tests\test_typed_memory.py tests\test_memory_daemon_ctl.py
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_typed_memory.py tests\test_memory_daemon_ctl.py tests\test_compactor.py tests\test_session_memory.py -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe scripts\memory_daemon_ctl.py status
```

Expected:

- Compile passes.
- Memory tests pass.
- CLI prints a JSON status object.
