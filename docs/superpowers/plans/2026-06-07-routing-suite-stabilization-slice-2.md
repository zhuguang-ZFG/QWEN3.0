# Routing Suite Stabilization Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the routing-adjacent pytest failures found after backend-aware skill reinjection.

**Architecture:** Keep production authority in `router_v3.py`, `routing_classifier.py`, and converter modules. Do not re-add removed private `server._...` helpers when tests can target the current authority module directly.

**Tech Stack:** Python 3.10, pytest, ruff, FastAPI routing helpers.

---

### Task 1: IDE Detection Single Source

**Files:**
- Modify: `router_v3.py`
- Modify: `routing_classifier.py`
- Test: `tests/test_routing_engine.py`
- Test: `tests/test_ide_detection.py`
- Test: `tests/test_backend_registry.py`

- [x] **Step 1: Add IDE fingerprints**

Add Claude Code, Continue, and Cursor entries to `router_v3._IDE_FINGERPRINTS` so `IDE_SOURCES` derives them automatically.

- [x] **Step 2: Share user-agent detection**

Add `router_v3.detect_ide_from_user_agent(text)` and call it from both `router_v3.classify_request()` and `routing_classifier.classify()`.

- [x] **Step 3: Verify IDE routing**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_classify_ide_from_ua tests/test_routing_engine.py::test_classify_continue_from_ua tests/test_routing_engine.py::test_classify_ide_from_system_prompt_fingerprint tests/test_ide_detection.py tests/test_backend_registry.py::test_router_v3_is_ide_sources_single_source -q --tb=short
```

Expected: all selected tests pass.

### Task 2: Code Pool Default Window

**Files:**
- Modify: `router_v3.py`
- Test: `tests/test_routing_engine.py`

- [x] **Step 1: Keep evaluated winners first**

Preserve the first four code strong backends: `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`.

- [x] **Step 2: Promote Cloudflare coder capacity into the default window**

Move `cf_qwen_coder` and `cfai_qwen_coder` immediately after the first four evaluated winners in `router_v3.POOLS["code"]["strong"]`.

- [x] **Step 3: Verify default selection**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_cloudflare_code_backends_enter_default_selection_window -q --tb=short
```

Expected: selected default backends include both Cloudflare coder entries.

### Task 3: Converter Boundary Tests

**Files:**
- Modify: `tests/test_routing_engine.py`
- Test: `tests/test_anthropic_preflight.py`

- [x] **Step 1: Import current converter authority**

Change the routing test to import `convert_messages_anthropic_to_openai` and `inject_anthropic_context_preflight` from `converters.anthropic_format`.

- [x] **Step 2: Keep server private helpers removed**

Do not add compatibility aliases to `server.py`; the production boundary is the converter module and `routes/tool_forward*.py`.

- [x] **Step 3: Verify converter behavior**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_anthropic_tool_route_injects_context_preflight tests/test_anthropic_preflight.py -q --tb=short
```

Expected: all selected tests pass.

### Task 4: Current Coding Scenario Semantics

**Files:**
- Modify: `tests/test_routing_engine.py`
- Modify: `routing_classifier.py` only if scenario classification no longer respects IDE sources
- Test: `tests/test_dual_track.py`
- Test: `tests/test_routing_engine.py`

- [x] **Step 1: Align E2E assertion with code orchestration**

Rename the `write a python sort function` E2E test and assert `request_type == "code_standard"`.

- [x] **Step 2: Ensure IDE source implies coding scenario**

Update `routing_classifier.classify_scenario()` to use `router_v3.IDE_SOURCES` for IDE-source forcing, not an OpenCode-only tuple.

- [x] **Step 3: Verify dual-track behavior**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_dual_track.py tests/test_routing_engine.py::test_route_e2e_coding_chat_uses_code_path -q --tb=short
```

Expected: all selected tests pass.

### Task 5: Slice Verification

**Files:**
- No additional files.

- [x] **Step 1: Run focused routing suite**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py tests/test_skills_injector.py tests/test_anthropic_preflight.py tests/test_ide_detection.py tests/test_backend_registry.py::test_router_v3_is_ide_sources_single_source -q --tb=short
```

Expected: all selected tests pass.

- [x] **Step 2: Run lint**

Run:

```powershell
ruff check router_v3.py routing_classifier.py routing_engine_skills.py skills_injector.py tests/test_routing_engine.py tests/test_skills_injector.py
```

Expected: `All checks passed!`

### Task 6: Anthropic Response Converter Boundary

**Files:**
- Modify: `tests/test_anthropic_tool_protocol.py`
- Test: `tests/test_anthropic_tool_protocol.py`

- [x] **Step 1: Import response converter from authority module**

Use `converters.anthropic_format.convert_response_openai_to_anthropic` for OpenAI-to-Anthropic response conversion assertions.

- [x] **Step 2: Keep SSE simulation server import scoped**

Leave `server._simulate_anthropic_sse` only for the SSE simulation test because that helper still lives in `server.py`.

- [x] **Step 3: Verify protocol tests**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_anthropic_tool_protocol.py -q --tb=short
```

Expected: all selected tests pass.

### Task 7: Overlay Backend Normalization

**Files:**
- Modify: `backends_registry.py`
- Modify: `routes/admin_backends_crud.py`
- Test: `tests/test_backend_registry.py`
- Test: `tests/test_admin_csrf.py`

- [x] **Step 1: Normalize overlay add/update entries**

When loading `data/backend_overrides.json`, copy each overlay config and fill defaults for `fmt`, `key`, `timeout`, `caps`, and `model`. If `model` is missing or empty, use the backend name.

- [x] **Step 2: Write admin add defaults**

When the admin CRUD route creates an overlay backend, write `model` as `body["model"]` or the backend name.

- [x] **Step 3: Verify registry and admin behavior**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_backend_registry.py::test_every_backend_has_fmt tests/test_backend_registry.py::test_every_backend_has_model tests/test_admin_csrf.py -q --tb=short
```

Expected: all selected tests pass.

### Task 8: OpenCode Fast Backend Prefix Semantics

**Files:**
- Modify: `tests/test_opencode_e2e.py`
- Test: `tests/test_opencode_e2e.py`

- [x] **Step 1: Align affinity assertion with prefix config**

`OPENCODE_FAST_BACKENDS` is used as a prefix set by `routing_selector.py`; assert `scnet_` instead of `scnet_ds_flash`.

- [x] **Step 2: Verify affinity test**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_opencode_e2e.py::test_opencode_backend_affinity -q --tb=short
```

Expected: selected test passes.

### Task 9: Health Tracker Reset Facade

**Files:**
- Modify: `health_tracker.py`
- Modify: `tests/test_health_tracker.py`
- Test: `tests/test_health_tracker.py`
- Test: `tests/test_health_bootstrap.py`

- [x] **Step 1: Export reset API**

Re-export `health_state.reset_all_state` from `health_tracker.py`.

- [x] **Step 2: Stop tests from touching split private dicts**

Update `tests/test_health_tracker.py` setup to call `health_tracker.reset_all_state()`.

- [x] **Step 3: Verify health tests**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_health_tracker.py tests/test_health_bootstrap.py -q --tb=short
```

Expected: all selected tests pass.

### Task 10: Budget Manager CF/Google Facade

**Files:**
- Modify: `budget_manager.py`
- Test: `tests/test_budget_cf_google.py`
- Test: `tests/test_budget_manager.py`

- [x] **Step 1: Re-export provider budget APIs**

Expose `CF_ACCOUNT_DAILY_LIMIT`, `CF_ACCOUNT_WARN_AT`, `get_cf_pool_usage`, `get_cf_pool_status`, `get_usage_summary`, and `get_total_requests_today` from `budget_manager.py`.

- [x] **Step 2: Verify budget behavior**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_budget_cf_google.py tests/test_budget_manager.py -q --tb=short
```

Expected: all selected tests pass.

### Task 11: Admin SSE Async Test Runner

**Files:**
- Modify: `tests/test_admin_logs_stream.py`
- Test: `tests/test_admin_logs_stream.py`

- [x] **Step 1: Replace manual event loop lookup**

Use `asyncio.run()` for local async helper execution instead of `asyncio.get_event_loop().run_until_complete(...)`.

- [x] **Step 2: Verify SSE publish helpers**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_admin_logs_stream.py -q --tb=short
```

Expected: publish tests pass and blocking SSE endpoint tests remain skipped.

### Task 12: Retrieval Injection Test Isolation

**Files:**
- Modify: `tests/test_retrieval_injection.py`
- Modify: `tests/test_routing_engine.py`
- Test: `tests/test_retrieval_injection.py`
- Test: `tests/test_routing_engine.py`

- [x] **Step 1: Patch the current retrieval authority**

Patch `context_pipeline.retrieval_injection.inject_retrieval_context`, which is dynamically imported by `routing_engine_context.inject_all_context()`.

- [x] **Step 2: Avoid speculative and skill reinjection interference**

Patch `speculative.classify_complexity` to return `complex` and patch `apply_backend_aware_skills` to identity in these tests.

- [x] **Step 3: Assert retrieval presence, not position**

Check that one message contains `[retrieval]` because enriched context and other system messages can precede retrieval.

- [x] **Step 4: Verify retrieval tests**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_retrieval_injection.py::test_routing_engine_reuses_shared_injector tests/test_routing_engine.py::test_route_uses_shared_retrieval_injection -q --tb=short
```

Expected: both selected tests pass.

### Task 13: Small Compatibility Facades

**Files:**
- Modify: `server.py`
- Modify: `scripts/deploy_unified.py`
- Test: `tests/test_chat_models.py`
- Test: `tests/test_request_stats.py`
- Test: `tests/test_security_closeout_regressions.py`

- [x] **Step 1: Re-export chat models**

Import `Message`, `ChatRequest`, and `extract_system_prompt` from `chat_models.py` in `server.py` for legacy callers.

- [x] **Step 2: Keep elapsed time patchable via server**

Define `server._elapsed_ms()` using `server.time.time()` so tests and route dependencies can patch the server facade.

- [x] **Step 3: Restore deploy command helper**

Add `scripts.deploy_unified._stop_port_8080_cmd()` as a pure command-builder function using POSIX-compatible `while` loops.

- [x] **Step 4: Verify compatibility tests**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_chat_models.py tests/test_request_stats.py::test_elapsed_ms_clamps_and_reports_real_duration tests/test_security_closeout_regressions.py::test_deploy_unified_stop_port_command_is_posix_shell_compatible -q --tb=short
```

Expected: all selected tests pass.

### Task 14: Chat Handler Monkeypatch Compatibility

**Files:**
- Modify: `routes/chat_handler.py`
- Modify: `tests/test_chat_ide_golden_path.py`
- Modify: `tests/test_prompt_memory_recall.py`
- Test: `tests/test_chat_ide_golden_path.py`
- Test: `tests/test_prompt_memory_recall.py`

- [x] **Step 1: Restore handler re-exports**

Re-export `needs_orchestration`, `v3_route`, and `quality_check` from `routes.chat_handler` for existing dispatch code and tests that monkeypatch the main handler module.

- [x] **Step 2: Keep tests off real OpenCode direct HTTP**

Patch `routes.chat_non_stream.OPENCODE_DIRECT_STREAM` to `False` in tests that mock `chat_handler.v3_route`.

- [x] **Step 3: Verify chat memory and evidence tests**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_chat_ide_golden_path.py::test_chat_golden_path_records_capability_evidence tests/test_prompt_memory_recall.py::test_handle_chat_applies_prompt_memory_before_routing tests/test_prompt_memory_recall.py::test_handle_chat_writes_and_recalls_same_header_session -q --tb=short
```

Expected: all selected tests pass.

### Task 15: Quality Gate Stable Failure Semantics

**Files:**
- Modify: `routes/quality_gate.py`
- Modify: `quality_gate.py`
- Test: `tests/test_quality_gate.py`
- Test: `tests/test_code_orchestrator.py`

- [x] **Step 1: Do not treat missing query as trivial**

Only apply the trivial-query short-answer exemption when `query` is non-empty.

- [x] **Step 2: Preserve stable syntax error reason code**

Add plain `python_syntax_error` alongside detailed syntax error reasons in root `quality_gate.py`.

- [x] **Step 3: Verify quality tests**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_quality_gate.py::test_quality_check_short_for_complex tests/test_quality_gate.py::test_typed_check_too_short_is_repairable tests/test_code_orchestrator.py::TestQualityGate::test_fail_syntax_error -q --tb=short
```

Expected: all selected tests pass.

### Task 16: Coding Pool Evidence Gate Fallback

**Files:**
- Modify: `coding_pool_admission.py`
- Test: `tests/test_enhance_context_pool_gate.py`
- Test: `tests/test_eval_pool_gate.py`
- Test: `tests/test_routing_facade.py`

- [x] **Step 1: Avoid empty coding pools**

If evidence gating filters every backend from a pool, return non-sandbox backends that survived eval demotion instead of an empty list.

- [x] **Step 2: Verify pool gate behavior**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_enhance_context_pool_gate.py tests/test_eval_pool_gate.py tests/test_routing_facade.py -q --tb=short
```

Expected: all selected tests pass.

### Task 12: Retrieval Injection Route Test Isolation

**Files:**
- Modify: `tests/test_retrieval_injection.py`
- Modify: `tests/test_routing_engine.py`
- Test: `tests/test_retrieval_injection.py`
- Test: `tests/test_routing_engine.py`

- [x] **Step 1: Patch the current retrieval authority**

Patch `context_pipeline.retrieval_injection.inject_retrieval_context`, because `routing_engine_context.inject_all_context()` imports it dynamically.

- [x] **Step 2: Isolate unrelated route injectors**

Patch `speculative.classify_complexity` to `"complex"` and `apply_backend_aware_skills` to identity so the test exercises standard execute.

- [x] **Step 3: Avoid brittle message index assertions**

Assert the retrieval message exists in the final messages instead of requiring it to be at index 0; enriched context can legitimately prepend system messages.

- [x] **Step 4: Verify retrieval route tests**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_retrieval_injection.py::test_routing_engine_reuses_shared_injector tests/test_routing_engine.py::test_route_uses_shared_retrieval_injection -q --tb=short
```

Expected: both selected tests pass.
