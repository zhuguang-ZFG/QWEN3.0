# Tool Dispatcher Clean Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining repository-admission quality risk by turning `tool_dispatcher.py` into a small facade and moving Telegram Function Calling tools into focused, clean modules.

**Architecture:** Keep the public API stable: `tool_dispatcher.execute_tool()`, `tool_dispatcher.get_tools_schema()`, `tool_dispatcher.run_fc_loop()`, `tool_dispatcher.stats()`, and `_get` remain importable. A new `lima_fc_tools` package owns registry, HTTP helper, FC loop, and category-specific tool modules. Tool descriptions and module comments are ASCII-only to avoid mojibake.

**Tech Stack:** Python stdlib, `httpx`, pytest.

---

## Files

- Create `lima_fc_tools/__init__.py`: package import surface and module registration.
- Create `lima_fc_tools/registry.py`: `tool`, `execute_tool`, `get_tools_schema`, `stats`.
- Create `lima_fc_tools/http_client.py`: shared async `_get`.
- Create `lima_fc_tools/fc_loop.py`: Function Calling loop.
- Create category modules under `lima_fc_tools/`: focused tool implementations under 300 lines each.
- Modify `tool_dispatcher.py`: compatibility facade under 120 lines.
- Modify `fc_caller.py` and `mimo_tts.py`: replace mojibake docstrings/comments with ASCII.
- Modify `tests/test_local_tool_modules.py`: add structural quality tests and preserve existing behavior tests.
- Modify `docs/superpowers/plans/2026-05-23-telegram-fc-tts-repo-admission.md`, `STATUS.md`, and `docs/LIMA_MEMORY.md`: update the admission conclusion.

## Tasks

- [x] Add failing tests that assert `tool_dispatcher.py`, `fc_caller.py`, `mimo_tts.py`, and `lima_fc_tools/*.py` are ASCII-only and each runtime file stays under 300 lines.
- [x] Add a regression test that exported tool names remain exactly the current 71-tool list.
- [x] Split registry, HTTP helper, and FC loop into focused modules.
- [x] Split tool implementations by category while keeping the same tool names and call signatures.
- [x] Replace mojibake tool descriptions with ASCII descriptions in the exported schema.
- [x] Keep `tool_dispatcher.py` as a compatibility facade for existing imports.
- [x] Run focused tests, compile checks, full pytest, secret scan, and `git diff --cached --check`.

## Result

- `tool_dispatcher.py` is now a compatibility facade.
- `lima_fc_tools/registry.py` owns registration and execution.
- `lima_fc_tools/http_client.py` owns shared HTTP GET behavior.
- `lima_fc_tools/fc_loop.py` owns the bounded Function Calling loop.
- Tool implementations are split across focused category modules, each under 300 lines.
- The exported 71 tool names are preserved and schema text is ASCII-only.

## Verification

- Focused local-tool/security/Telegram suite: `23 passed`.
- Compile checks: `py_compile` and `compileall` passed for the facade, new package, Telegram modules, routes, and tests.
- Ruff check passed for the facade, new package, Telegram modules, and local-tool tests.
- Full pytest: `418 passed, 8 skipped`.
- Secret scan over the admitted tool files returned no matches.
