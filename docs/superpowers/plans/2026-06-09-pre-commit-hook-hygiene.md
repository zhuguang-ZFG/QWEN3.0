# Pre-Commit Hook Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the local pre-commit hook's wrong full-suite command with a tracked, fast, deterministic LiMa gate.

**Architecture:** Add a repository-tracked Python wrapper for pre-commit checks, then point the local `.git/hooks/pre-commit.ps1` at that wrapper. The default hook runs quick deterministic gates only: staged whitespace, tracked-file ruff, and staged Python compile. The wrapper also exposes `--full` for the documented CI-style pytest command with long/external tests ignored.

**Tech Stack:** Python 3.10, subprocess, pytest, ruff, Git staged-file discovery, local Git hook wrapper.

---

## File Structure

- Create: `scripts/run_pre_commit_check.py` for quick and optional full hook gates.
- Modify: `tests/test_ci_gates.py` for unit coverage of the pre-commit wrapper.
- Modify locally only: `.git/hooks/pre-commit.ps1` to call the tracked wrapper. This file is not committed.
- Update: `STATUS.md`, `progress.md`, and `findings.md` with closeout evidence.

## Tasks

### Task 1: Add Tracked Hook Wrapper

**Files:**
- Create: `scripts/run_pre_commit_check.py`
- Modify: `tests/test_ci_gates.py`

- [x] Add tests proving staged Python discovery filters only staged `.py` / `.pyi` paths.
- [x] Add tests proving quick mode runs tracked ruff, staged diff check, and staged Python compile.
- [x] Add tests proving full mode uses the documented pytest ignore list.
- [x] Implement the wrapper with quick default and `--full` option.

### Task 2: Install Local Hook

**Files:**
- Modify local-only: `.git/hooks/pre-commit.ps1`

- [x] Replace direct `pytest tests/` and `ruff check .` calls with `python scripts/run_pre_commit_check.py`.
- [x] Keep fail-closed behavior if `.venv310` or the wrapper is unavailable.
- [x] Run the local hook script directly.

### Task 3: Validate And Close Out

**Files:**
- Modify: `STATUS.md`
- Modify: `progress.md`
- Modify: `findings.md`

- [x] Run focused pytest for CI gate tests.
- [x] Run `python scripts/run_pre_commit_check.py`.
- [x] Run `python scripts/run_pre_commit_check.py --full` or document why it was not rerun if an equivalent fresh full gate already exists.
- [x] Run ruff/py_compile on touched files.
- [ ] Run `git diff --check` and staged secret scan.
- [ ] Commit and push GitHub `origin`; record Gitee remote status.
